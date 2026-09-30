package biz.boskovic.opus.player

import android.app.Activity
import android.graphics.Color
import android.hardware.display.DisplayManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.view.Display
import android.view.SurfaceHolder
import android.view.SurfaceView
import android.view.View
import androidx.annotation.OptIn
import androidx.core.net.toUri
import androidx.media3.common.C
import androidx.media3.common.ForwardingPlayer
import androidx.media3.common.Format
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.TrackSelectionOverride
import androidx.media3.common.Tracks
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.DecoderReuseEvaluation
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.analytics.AnalyticsListener
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.MediaSession
import androidx.media3.ui.CaptionStyleCompat
import androidx.media3.ui.PlayerView
import biz.boskovic.opus.core.Opus
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import kotlin.math.abs
import kotlin.math.roundToInt

/** The decoder, and nothing above it.
 *
 * What a browser cannot do is open a Matroska file and decode HEVC on this box's
 * own hardware. That is all this is for. It draws onto a surface that sits
 * BEHIND the page, so the transport, the track menus and the clock stay the ones
 * the rest of OPUS already has — one set of controls, not a second set that
 * drifts from the first. */
@OptIn(UnstableApi::class)
class Engine(private val host: Activity, private val screen: PlayerView) {

    private var player: ExoPlayer? = null

    /** The picture goes to a SurfaceView, and a SurfaceView keeps its last
     * frame in a plane of the compositor's own, under the shutter the stage
     * closes over it. The panel relocking showed that plane on its own for a
     * moment: a frame of the last film in front of the next. So the stage is
     * taken down with the film — hidden, Android releases the surface and the
     * frame with it — and put up again for the next one, which begins once the
     * new surface is there, a traversal later. */
    private val stage: SurfaceView get() = screen.videoSurfaceView as SurfaceView
    private var staged: (() -> Unit)? = null

    init {
        stage.holder.addCallback(object : SurfaceHolder.Callback {
            override fun surfaceCreated(holder: SurfaceHolder) {
                staged?.let {
                    staged = null
                    it()
                }
            }
            override fun surfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) = Unit
            override fun surfaceDestroyed(holder: SurfaceHolder) = Unit
        })
    }

    private fun onStage(then: () -> Unit) {
        staged = null
        stage.visibility = View.VISIBLE
        if (stage.holder.surface.isValid) then() else staged = then
    }

    /** The box's own record of what is playing. Without one, the remote's media
     * keys, the system and the house reading the box all saw an app with nothing
     * in it — play and pause pressed on a remote reached nobody. */
    private var session: MediaSession? = null

    /** What the page says is about to play: the title and the picture the
     * session shows, kept until the next film or song says otherwise. */
    private var meta: MediaMetadata = MediaMetadata.EMPTY

    /** Where the keys the engine cannot answer by itself go: next, previous and
     * stop mean a song in a queue or a chapter in a film, which only the page
     * knows. Play and pause the engine answers on its own. */
    var onKey: ((String) -> Unit)? = null

    /** Media3 refuses to be read from any thread but the one that made it, and
     * the page asks from the bridge's own. So the answer is kept up to date here,
     * on the right thread, and handed over already written. */
    @Volatile private var snapshot: String = "{}"

    /** What is actually decoding, said by the thing that chose it. A panel that
     * claims hardware because someone typed hardware is worth nothing. */
    @Volatile private var decoder: String = ""
    @Volatile private var dropped: Int = 0
    @Volatile private var picture: String = ""

    /** What the catalogue says the file runs at. The container usually does not
     * say, and a rate nobody knows is a rate nobody can ask a panel to match. */
    @Volatile private var declared: Float = 0f

    /** Said to the page, which puts it on the screen: a film that cannot be
     * shown is a message, not a black panel with the sound running on. */
    @Volatile private var failure: String = ""

    /** What happened to this film, in order. The box keeps its own log for a few
     * hours at most, so a picture that never came was unexplainable by the
     * next morning; this goes to the server whenever something went wrong. */
    private val trace = ArrayList<String>()
    private var openedAt = 0L
    private var troubled = false

    /** When the decoder last put a picture on the surface while the film was
     * playing. A film that says it is playing and draws nothing is only its
     * sound — whether the decoder never started, or every frame arrives too
     * late for a clock the sound has run away with. */
    private var drawn = -1
    private var drawnAt = 0L
    private var reopened = false
    private var opening: Opening? = null

    private class Opening(
        val url: String,
        val subtitles: List<Sidecar>,
        val preferAudio: String,
        val preferText: String,
    )

    private val beat = Handler(Looper.getMainLooper())
    private val tick = object : Runnable {
        override fun run() {
            watchPicture()
            snapshot = look()
            beat.postDelayed(this, 300)
        }
    }

    fun state(): String = snapshot

    private fun note(what: String) {
        val at = if (openedAt == 0L) 0L else SystemClock.elapsedRealtime() - openedAt
        if (trace.size >= TRACE) trace.removeAt(0)
        trace.add("+${at}ms $what")
        Log.i(TAG, what)
    }

    private fun trouble(what: String) {
        troubled = true
        note(what)
        Log.w(TAG, what)
    }

    /** How a subtitle should look from a sofa: white, outlined, and big enough
     * to read without leaning in. The platform's own caption settings are a
     * phone's answer to this and most televisions never have them touched. */
    private fun captions() {
        screen.subtitleView?.apply {
            setStyle(
                CaptionStyleCompat(
                    Color.WHITE,
                    Color.TRANSPARENT,
                    Color.TRANSPARENT,
                    CaptionStyleCompat.EDGE_TYPE_OUTLINE,
                    Color.BLACK,
                    null,
                )
            )
            setApplyEmbeddedStyles(false)
            setFractionalTextSize(0.055f)
        }
        raiseCaptions(false)
    }

    /** Out from behind the bar while the bar is up. A line of dialogue printed
     * over the controls is a line nobody reads. */
    fun raiseCaptions(raised: Boolean) {
        screen.subtitleView?.setBottomPaddingFraction(if (raised) 0.20f else 0.08f)
    }

    /** What is playing, as the page names it. Applied to the item already
     * playing as well, so a description that arrives a moment late is not lost. */
    fun describe(title: String, artist: String, album: String, art: String) {
        meta = MediaMetadata.Builder()
            .setTitle(title.ifBlank { null })
            .setArtist(artist.ifBlank { null })
            .setAlbumTitle(album.ifBlank { null })
            .setArtworkUri(art.takeIf { it.startsWith("http") }?.toUri())
            .build()
        val engine = player ?: return
        val current = engine.currentMediaItem ?: return
        engine.replaceMediaItem(
            engine.currentMediaItemIndex,
            current.buildUpon().setMediaMetadata(meta).build(),
        )
    }

    /** The engine as the session sees it: next, previous, stop and the skips
     * are always offered, and handed to the page instead of to a playlist the
     * engine does not have. The page owns the skip's length, so fast-forward is
     * the same step as an arrow over the film rather than the engine's own. */
    private inner class Keyed(engine: Player) : ForwardingPlayer(engine) {
        override fun getAvailableCommands(): Player.Commands =
            super.getAvailableCommands().buildUpon()
                .addAll(*HANDED)
                .build()

        override fun isCommandAvailable(command: Int): Boolean =
            command in HANDED || super.isCommandAvailable(command)

        override fun seekToNext() { onKey?.invoke("next") }
        override fun seekToNextMediaItem() { onKey?.invoke("next") }
        override fun seekToPrevious() { onKey?.invoke("previous") }
        override fun seekToPreviousMediaItem() { onKey?.invoke("previous") }
        override fun stop() { onKey?.invoke("stop") }
        override fun seekForward() { onKey?.invoke("forward") }
        override fun seekBack() { onKey?.invoke("back") }
    }

    private fun look(): String = JSONObject()
        .put("position", position())
        .put("duration", duration())
        .put("playing", playing())
        .put("ended", ended())
        .put("audio", tracks(AUDIO))
        .put("text", tracks(TEXT))
        .put("decoder", decoder)
        .put("dropped", dropped)
        .put("picture", picture)
        .put("error", failure)
        .toString()

    private val sources = DefaultDataSource.Factory(host, OkHttpDataSource.Factory(PlayerApp.http(host)))

    private val displays = host.getSystemService(DisplayManager::class.java)
    private var awaiting: DisplayManager.DisplayListener? = null
    private val gaveUp = Runnable { settled() }
    private var onSettled: (() -> Unit)? = null

    /** The panel keeps a film's rate once the film is over. Handing it back at
     * every stop cost a relock of the HDMI chain (1.7 s behind the amplifier)
     * with the menu waiting behind it, and one more when the next episode asked
     * for the same rate again. It goes back to the box's own mode when the page
     * leaves the front — the screensaver, another app — while nobody is looking,
     * so the page returns at that mode and not behind yet another relock. */
    fun leave() {
        if (player == null) switchPanel(0, quietly = false)
    }

    /** Told true while the panel is changing mode and false once it has. An HDMI
     *  chain can take seconds to relock (11.6 s behind the amplifier once, against
     *  0.3 s as a rule), and while it does the compositor takes no frames: a page
     *  that draws then holds the main thread in its draw, the remote's keys wait,
     *  and Android declares the app dead. The page is taken off the screen for the
     *  switch so there is nothing to draw, and the keys are not taken meanwhile. */
    var onQuiet: ((Boolean) -> Unit)? = null
    private var quiet = false
    /** the mode the box was on before a film asked for its own: what handing back
     *  to 0 returns to, known here because a Display does not say its default */
    private var homeMode = -1
    private var asking = 0
    private val applyMode = Runnable {
        host.window.attributes = host.window.attributes.apply { preferredDisplayModeId = asking }
    }
    private val speak: Runnable = Runnable {
        if (!quiet) return@Runnable
        quiet = false
        displays.unregisterDisplayListener(quietWatch)
        beat.removeCallbacks(tooLong)
        onQuiet?.invoke(false)
    }
    private val tooLong: Runnable = Runnable {
        trouble("panel still changing mode after ${QUIET_MAX_MS} ms; the page is shown again")
        speak.run()
    }
    private val quietWatch: DisplayManager.DisplayListener = object : DisplayManager.DisplayListener {
        override fun onDisplayChanged(displayId: Int) {
            if (displayId != screen.display?.displayId) return
            beat.removeCallbacks(speak)
            beat.postDelayed(speak, QUIET_AFTER_MS)
        }
        override fun onDisplayAdded(displayId: Int) = Unit
        override fun onDisplayRemoved(displayId: Int) = Unit
    }

    private fun switchPanel(modeId: Int, quietly: Boolean) {
        beat.removeCallbacks(applyMode)
        val display = screen.display
        if (host.window.attributes.preferredDisplayModeId == 0) homeMode = display?.mode?.modeId ?: -1
        val arriving = if (modeId == 0) homeMode else modeId
        if (host.window.attributes.preferredDisplayModeId == modeId) {
            // a switch cancelled above before it was applied leaves a quiet
            // waiting on a display event that is never coming
            if (quiet && display?.mode?.modeId == arriving) speak.run()
            return
        }
        asking = modeId
        // no change of mode means no display event to end the quiet on
        if (!quietly || display == null || display.mode.modeId == arriving) {
            applyMode.run()
            return
        }
        if (!quiet) {
            quiet = true
            displays.registerDisplayListener(quietWatch, beat)
            onQuiet?.invoke(true)
        }
        beat.removeCallbacks(tooLong)
        beat.postDelayed(tooLong, QUIET_MAX_MS)
        // the frame without the page is drawn before the switch begins
        beat.postDelayed(applyMode, QUIET_FRAME_MS)
    }

    /** A panel that changes mode under a playing film — asked for by us when the
     * catalogue did not know the rate, or by an amplifier renegotiating the HDMI
     * link — leaves the passthrough sound rebuilt against a clock the picture no
     * longer follows. Seeking to where the film is rebuilds both. */
    private var playingOn = -1
    private val panelWatch = object : DisplayManager.DisplayListener {
        override fun onDisplayChanged(displayId: Int) {
            val engine = player ?: return
            val display = screen.display ?: return
            if (displayId != display.displayId || onSettled != null || display.mode.modeId == playingOn) return
            playingOn = display.mode.modeId
            note("panel changed to ${display.mode} while playing; resynchronising")
            engine.seekTo(engine.currentPosition)
        }
        override fun onDisplayAdded(displayId: Int) = Unit
        override fun onDisplayRemoved(displayId: Int) = Unit
    }

    class Sidecar(val url: String, val lang: String, val label: String)

    fun open(
        url: String,
        startSeconds: Double,
        subtitles: List<Sidecar>,
        preferAudio: String,
        preferText: String,
        declaredRate: Float,
    ) {
        if (opening != null) report()
        stopPlayer()
        declared = declaredRate
        trace.clear()
        troubled = false
        reopened = false
        openedAt = SystemClock.elapsedRealtime()
        failure = ""
        opening = Opening(url, subtitles, preferAudio, preferText)
        note("open at ${startSeconds}s, declared rate $declaredRate, panel ${screen.display?.mode}")
        // The film is read, buffered and decoded while the panel changes mode,
        // without its sound: a passthrough AudioTrack built before the switch
        // dies under it ("dead IAudioTrack, Offloaded or Direct"), and the one
        // rebuilt in its place runs behind the picture for the whole film. The
        // sound joins once the panel has settled, with the picture already
        // decoded and waiting for it.
        val mode = modeFor(declaredRate)
        onStage {
            begin(startSeconds, silent = mode != null && !standsOn(mode))
            onPanel(mode) { sound() }
        }
    }

    private fun begin(startSeconds: Double, silent: Boolean) {
        val with = opening ?: return
        val item = MediaItem.Builder()
            .setUri(with.url.toUri())
            .setSubtitleConfigurations(with.subtitles.map(::sidecar))
            .setMediaMetadata(meta)
            .build()
        decoder = ""
        dropped = 0
        picture = ""
        captions()
        // A film narrower than the panel is framed in black, not in the colour
        // the library is drawn on.
        screen.setBackgroundColor(Color.BLACK)
        val engine = ExoPlayer.Builder(host, Renderers(host))
            .setMediaSourceFactory(DefaultMediaSourceFactory(sources))
            .setAudioAttributes(Box.SOUND, true)
            .build()
        player = engine
        screen.player = engine
        engine.addListener(object : Player.Listener {
            override fun onIsPlayingChanged(isPlaying: Boolean) = awake()

            override fun onTracksChanged(tracks: Tracks) {
                awake()
                val video = tracks.groups.any { it.type == C.TRACK_TYPE_VIDEO }
                if (video && !tracks.isTypeSelected(C.TRACK_TYPE_VIDEO)) {
                    fail("the picture track was not taken: ${tracks.groups.filter { it.type == C.TRACK_TYPE_VIDEO }.joinToString { it.getTrackFormat(0).toString() }}")
                }
            }

            override fun onPlaybackStateChanged(playbackState: Int) {
                note("state ${STATES[playbackState] ?: playbackState}")
            }

            override fun onRenderedFirstFrame() = note("first picture")

            override fun onPlayerError(error: PlaybackException) {
                Log.e(TAG, "playback failed", error)
                fail("${error.errorCodeName}: ${error.message ?: error.cause?.message ?: ""}")
            }
        })
        engine.addAnalyticsListener(object : AnalyticsListener {
            override fun onVideoDecoderInitialized(
                eventTime: AnalyticsListener.EventTime,
                decoderName: String,
                initializedTimestampMs: Long,
                initializationDurationMs: Long,
            ) {
                decoder = decoderName
                note("video decoder $decoderName")
            }

            override fun onAudioDecoderInitialized(
                eventTime: AnalyticsListener.EventTime,
                decoderName: String,
                initializedTimestampMs: Long,
                initializationDurationMs: Long,
            ) {
                note("audio decoder $decoderName")
            }

            override fun onDroppedVideoFrames(
                eventTime: AnalyticsListener.EventTime,
                droppedFrames: Int,
                elapsedMs: Long,
            ) {
                dropped += droppedFrames
            }

            override fun onVideoInputFormatChanged(
                eventTime: AnalyticsListener.EventTime,
                format: Format,
                evaluation: DecoderReuseEvaluation?,
            ) {
                picture = format.width.toString() + "×" + format.height.toString()
                // The catalogue did not know the rate, so the switch lands on a
                // film already playing; the panel watch resynchronises it.
                if (declared <= 0f && format.frameRate > 0) {
                    modeFor(format.frameRate)?.let { ask(it) }
                }
            }
        })
        // The house's answer to which language, and — left to itself — the
        // selector will not choose a track this box has no way to render, so
        // the two rules do not have to be written twice.
        engine.trackSelectionParameters = engine.trackSelectionParameters
            .buildUpon()
            .setPreferredAudioLanguage(with.preferAudio.ifBlank { null })
            .setPreferredTextLanguage(with.preferText.ifBlank { null })
            .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, silent)
            .build()
        // Left on, the player casts its own vote on this surface, and only for
        // a change it judges seamless — which sixty to twenty-four over HDMI
        // never is. The rate is ours to ask for, in modeFor().
        engine.videoChangeFrameRateStrategy = C.VIDEO_CHANGE_FRAME_RATE_STRATEGY_OFF
        engine.setMediaItem(item, (startSeconds * 1000).toLong())
        engine.prepare()
        engine.playWhenReady = !silent
        playingOn = screen.display?.mode?.modeId ?: -1
        displays.registerDisplayListener(panelWatch, beat)
        session = MediaSession.Builder(host, Keyed(engine)).setId(SESSION).build()
        beat.removeCallbacks(tick)
        beat.post(tick)
    }

    /** Sound with no picture is what a viewer sees of a decoder that never drew,
     * a surface that went away under it, or a panel that changed mode as the film
     * began. Stopping and playing again always cured it, so the engine does that
     * once by itself; a second time is said out loud instead of retried. */
    private fun watchPicture() {
        val engine = player ?: return
        val now = SystemClock.elapsedRealtime()
        if (!engine.isPlaying || !showsPicture()) {
            drawnAt = 0L
            return
        }
        val counters = engine.videoDecoderCounters?.also { it.ensureUpdated() }
        val count = counters?.renderedOutputBufferCount ?: 0
        if (drawnAt == 0L || count != drawn) {
            drawn = count
            drawnAt = now
            return
        }
        val waited = now - drawnAt
        if (waited < PICTURE_MS) return
        val why = "no picture drawn for ${waited}ms while the sound plays " +
            "(decoder $decoder, dropped ${counters?.droppedBufferCount ?: 0}, " +
            "surface ${(screen.videoSurfaceView as? SurfaceView)?.holder?.surface?.isValid}, " +
            "panel ${screen.display?.mode})"
        drawnAt = 0L
        if (reopened) {
            fail(why)
            return
        }
        trouble("$why; opening again")
        reopened = true
        val at = engine.currentPosition / 1000.0
        stopPlayer()
        // a panel still on its way brings the sound with it when it arrives
        onStage { begin(at, silent = onSettled != null) }
    }

    /** The film is waiting for a screen the box could not take: the stage
     *  exists only in front, and it stays behind until somebody opens OPUS. */
    fun unseen() = fail("the box could not come to the front: it is neither Home nor allowed to draw over other apps")

    private fun fail(why: String) {
        failure = why
        trouble(why)
    }

    private fun sidecar(track: Sidecar): MediaItem.SubtitleConfiguration =
        MediaItem.SubtitleConfiguration.Builder(track.url.toUri())
            .setMimeType(MimeTypes.TEXT_VTT)
            .setLanguage(track.lang.ifBlank { null })
            .setLabel(track.label.ifBlank { null })
            .build()

    private fun playing(): Boolean = player?.isPlaying ?: false

    private fun showsPicture(): Boolean =
        player?.currentTracks?.isTypeSelected(C.TRACK_TYPE_VIDEO) == true

    /** A film keeps the panel awake while it plays; music leaves the box free
     *  to fall to its screensaver. */
    private fun awake() {
        screen.keepScreenOn = playing() && showsPicture()
    }

    /** The activity has left the screen. A film nobody can see stops; music
     *  goes on, which is what putting a record on means. */
    fun hidden() {
        if (showsPicture()) player?.pause()
    }

    /** The page that was driving a film is gone — its renderer died or it was
     *  loaded again — and the page that replaces it has no film on it. A film
     *  left running under that page is sound behind a screen of posters with
     *  no way to stop it, so it stops; music carries on, since the new page
     *  takes a record back up by itself. */
    fun orphaned() {
        if (!showsPicture()) return
        note("the page that was playing this film is gone")
        stop()
    }

    /** Something plays that nobody would want a dialog over. */
    fun busy(): Boolean = player != null

    fun toggle() {
        val engine = player ?: return
        if (engine.isPlaying) engine.pause() else engine.play()
    }

    fun seek(seconds: Double) {
        player?.seekTo((seconds * 1000).toLong())
    }

    private fun position(): Double = (player?.currentPosition ?: 0L) / 1000.0

    private fun duration(): Double {
        val length = player?.duration ?: C.TIME_UNSET
        return if (length == C.TIME_UNSET) 0.0 else length / 1000.0
    }

    private fun ended(): Boolean = player?.playbackState == Player.STATE_ENDED

    /** What is in the file, as the thing playing it sees it — so the list on the
     * screen and the track that changes are the same list. */
    private fun tracks(type: Int): JSONArray {
        val out = JSONArray()
        val groups = player?.currentTracks?.groups ?: return out
        var index = 0
        for (group in groups) {
            if (group.type != type) continue
            for (i in 0 until group.length) {
                val format = group.getTrackFormat(i)
                out.put(
                    JSONObject()
                        .put("index", index)
                        .put("lang", format.language ?: "")
                        .put("label", format.label ?: "")
                        .put("channels", format.channelCount.takeIf { it > 0 } ?: JSONObject.NULL)
                        .put("codec", (format.sampleMimeType ?: "").substringAfterLast('/'))
                        .put("chosen", group.isTrackSelected(i))
                )
                index += 1
            }
        }
        return out
    }

    fun choose(type: Int, wanted: Int) {
        val engine = player ?: return
        if (wanted < 0) {
            engine.trackSelectionParameters = engine.trackSelectionParameters
                .buildUpon()
                .setTrackTypeDisabled(type, true)
                .build()
            return
        }
        var index = 0
        for (group in engine.currentTracks.groups) {
            if (group.type != type) continue
            for (i in 0 until group.length) {
                if (index == wanted) {
                    engine.trackSelectionParameters = engine.trackSelectionParameters
                        .buildUpon()
                        .setTrackTypeDisabled(type, false)
                        .setOverrideForType(TrackSelectionOverride(group.mediaTrackGroup, i))
                        .build()
                    return
                }
                index += 1
            }
        }
    }

    /** The panel mode that runs a film at its own rate: one blink is worth two
     * hours of twenty-four frames a second shown in sixty, which is what judder is.
     *
     * Asked as a display mode on the window, not as a frame rate on the surface.
     * The Shield ships with `ro.vendor.surface_flinger.use_frame_rate_api=false`
     * and runs Android 11, so Surface.setFrameRate never reaches its compositor
     * and the panel stayed at sixty; a preferred mode is honoured on every box.
     * The resolution the box already runs at is kept — only the rate changes. */
    private fun modeFor(rate: Float): Display.Mode? {
        if (rate <= 0f) return null
        val display = screen.display ?: return null
        val now = display.mode
        val same = display.supportedModes.filter {
            it.physicalWidth == now.physicalWidth && it.physicalHeight == now.physicalHeight
        }
        return same.firstOrNull { abs(it.refreshRate - rate) < 0.01f }
            ?: same.filter {
                val times = it.refreshRate / rate
                times >= 2f && abs(times - times.roundToInt()) < 0.001f
            }.minByOrNull { it.refreshRate }
    }

    private fun standsOn(mode: Display.Mode): Boolean {
        val display = screen.display ?: return true
        return display.mode.modeId == mode.modeId &&
            host.window.attributes.preferredDisplayModeId == mode.modeId
    }

    private fun ask(mode: Display.Mode) {
        switchPanel(mode.modeId, quietly = true)
    }

    /** The panel is where the film wants it: the sound joins and the film runs. */
    private fun sound() {
        val engine = player ?: return
        playingOn = screen.display?.mode?.modeId ?: -1
        engine.trackSelectionParameters = engine.trackSelectionParameters
            .buildUpon()
            .setTrackTypeDisabled(C.TRACK_TYPE_AUDIO, false)
            .build()
        engine.playWhenReady = true
    }

    /** Ask for the mode, and carry on once the panel is there and staying there.
     *
     * The panel being at the mode is not enough on its own: a hand-back asked a
     * moment earlier may still be on its way, and a film begun then is a film the
     * switch lands on. When the panel already stands at the mode, it has to stay
     * still for a short while before the film starts. A panel that never answers
     * is still a film somebody is waiting for, so after a few seconds it plays at
     * whatever rate the box is on — and says so. */
    private fun onPanel(mode: Display.Mode?, then: () -> Unit) {
        forgetPanel()
        val display = screen.display
        if (mode == null || display == null || standsOn(mode)) {
            then()
            return
        }
        onSettled = then
        val still = Runnable { if (display.mode.modeId == mode.modeId) settled() }
        awaiting = object : DisplayManager.DisplayListener {
            override fun onDisplayChanged(displayId: Int) {
                if (displayId != display.displayId) return
                beat.removeCallbacks(still)
                if (display.mode.modeId == mode.modeId) settled()
            }
            override fun onDisplayAdded(displayId: Int) = Unit
            override fun onDisplayRemoved(displayId: Int) = Unit
        }.also { displays.registerDisplayListener(it, beat) }
        beat.postDelayed(gaveUp, 5_000)
        if (display.mode.modeId == mode.modeId) beat.postDelayed(still, STILL_MS)
        note("asking the panel for $mode")
        ask(mode)
    }

    private fun settled() {
        val then = onSettled ?: return
        val mode = screen.display?.mode
        if (mode?.modeId != host.window.attributes.preferredDisplayModeId) {
            trouble("panel did not reach mode ${host.window.attributes.preferredDisplayModeId}; playing at $mode")
        } else {
            note("panel at $mode")
        }
        forgetPanel()
        then()
    }

    private fun forgetPanel() {
        beat.removeCallbacks(gaveUp)
        awaiting?.let { displays.unregisterDisplayListener(it) }
        awaiting = null
        onSettled = null
    }

    private fun stopPlayer() {
        beat.removeCallbacks(tick)
        displays.unregisterDisplayListener(panelWatch)
        snapshot = "{}"
        screen.keepScreenOn = false
        session?.release()
        session = null
        staged = null
        screen.player = null
        player?.release()
        player = null
        stage.visibility = View.INVISIBLE
        drawn = -1
        drawnAt = 0L
    }

    private fun end() {
        forgetPanel()
        if (opening != null) {
            note("stopped")
            report()
        }
        opening = null
        stopPlayer()
        screen.setBackgroundColor(Color.TRANSPARENT)
    }

    /** The page is done with this film. The panel stays at the film's rate and
     *  the menu is there at once; see [leave]. */
    fun stop() {
        end()
    }

    /** The activity is going; nothing follows, so the panel is handed back now. */
    fun release() {
        end()
        speak.run()
        switchPanel(0, quietly = false)
    }

    /** A film that went wrong tells the server what happened to it, from the
     *  open to the stop, so the next morning it can still be explained. */
    private fun report() {
        if (!troubled) return
        val body = JSONObject()
            .put("app", host.packageName)
            .put("version", Opus.versionName(host))
            .put("device", "${Build.MANUFACTURER} ${Build.MODEL} / Android ${Build.VERSION.RELEASE}")
            .put("url", opening?.url?.substringBefore('?') ?: "")
            .put("events", JSONArray(trace))
            .toString()
        val client = PlayerApp.http(host)
        Thread {
            val request = Request.Builder()
                .url(Opus.url("/api/app/playback-report"))
                .post(body.toRequestBody("application/json; charset=utf-8".toMediaType()))
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    if (!response.isSuccessful) Log.w(TAG, "playback report refused: HTTP ${response.code}")
                }
            } catch (failure: IOException) {
                Log.w(TAG, "playback report not sent", failure)
            }
        }.start()
    }

    companion object {
        private const val TAG = "OpusEngine"
        /** One session at a time, released before the next is made, so one name. */
        private const val SESSION = "opus-tv"
        const val AUDIO = C.TRACK_TYPE_AUDIO
        const val TEXT = C.TRACK_TYPE_TEXT
        private const val STILL_MS = 800L
        private const val QUIET_FRAME_MS = 50L
        private const val QUIET_AFTER_MS = 300L
        private const val QUIET_MAX_MS = 20_000L
        /** Long enough for a decoder that is merely slow and a panel that is
         *  still locking; short enough that nobody has reached for the remote. */
        private const val PICTURE_MS = 4_000L
        private const val TRACE = 200
        private val HANDED = intArrayOf(
            Player.COMMAND_SEEK_TO_NEXT,
            Player.COMMAND_SEEK_TO_PREVIOUS,
            Player.COMMAND_STOP,
            Player.COMMAND_SEEK_FORWARD,
            Player.COMMAND_SEEK_BACK,
        )
        private val STATES = mapOf(
            Player.STATE_IDLE to "idle",
            Player.STATE_BUFFERING to "buffering",
            Player.STATE_READY to "ready",
            Player.STATE_ENDED to "ended",
        )
    }
}
