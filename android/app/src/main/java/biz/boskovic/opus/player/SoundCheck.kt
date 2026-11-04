package biz.boskovic.opus.player

import android.content.Context
import android.content.IntentFilter
import android.hardware.display.DisplayManager
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.view.Display
import androidx.annotation.OptIn
import androidx.core.content.edit
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.audio.AudioCapabilities
import org.json.JSONObject
import java.nio.ByteBuffer
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.TimeoutException

/** Which surround formats really leave this box, found by playing a moment of
 *  silence in each instead of asking.
 *
 *  Android asks the audio HAL, and a HAL can claim a format it cannot play: the
 *  Xiaomi stick's MS12 claims TrueHD, takes the stream and never starts its
 *  clock, so the picture waits for a sound that never comes. An answer is kept
 *  against everything that could change it (what is plugged in, the box's sound
 *  settings, its firmware), so another amplifier or television is checked again
 *  and the same one never twice. */
@OptIn(UnstableApi::class)
object SoundCheck {

    private class Kind(val mime: String, val encoding: Int, val most: Int, val sample: Int, val buffer: Int)

    /** The buffers are Media3's own passthrough sizes, so the check opens the
     *  output the way the engine will; [Kind.most] is what the format itself
     *  carries, since the platform's claim is the output's and AC3 at 7.1 is
     *  refused by every box. */
    private val KINDS = mapOf(
        "ac3" to Kind(MimeTypes.AUDIO_AC3, AudioFormat.ENCODING_AC3, 6, R.raw.silence_ac3, 40_000),
        "eac3" to Kind(MimeTypes.AUDIO_E_AC3, AudioFormat.ENCODING_E_AC3, 8, R.raw.silence_eac3, 192_000),
        "dts" to Kind(MimeTypes.AUDIO_DTS, AudioFormat.ENCODING_DTS, 6, R.raw.silence_dts, 48_000),
        "truehd" to Kind(MimeTypes.AUDIO_TRUEHD, AudioFormat.ENCODING_DOLBY_TRUEHD, 8, R.raw.silence_truehd, 765_625),
    )

    private sealed interface Outcome {
        data class Started(val ms: Long) : Outcome
        data object Silent : Outcome
        data object Refused : Outcome
    }

    private val KIND_OF_MIME = mapOf(
        MimeTypes.AUDIO_AC3 to "ac3",
        MimeTypes.AUDIO_E_AC3 to "eac3",
        MimeTypes.AUDIO_E_AC3_JOC to "eac3",
        MimeTypes.AUDIO_DTS to "dts",
        MimeTypes.AUDIO_DTS_HD to "dts",
        MimeTypes.AUDIO_DTS_EXPRESS to "dts",
        MimeTypes.AUDIO_DTS_UHD_P2 to "dts",
        MimeTypes.AUDIO_TRUEHD to "truehd",
    )

    /** The settings boxes keep their surround choice in: Android's own, and
     *  Amlogic's digital output mode. */
    private val SETTINGS = listOf(
        "encoded_surround_output",
        "encoded_surround_output_enabled_formats",
        "digital_audio_format",
    )

    /** Raised when the check itself changes, so every box checks again. */
    private const val METHOD = 3
    private const val LISTEN_MS = 2_500L
    private const val POLL_MS = 10L
    private const val SETTLE_MS = 500L
    private const val OPEN_MS = 1_000L
    private const val WAIT_MS = 12_000L
    private const val KEPT = 8
    private const val STORE = "sound_check"
    private const val HEARD = "heard"
    private const val TAG = "OpusSound"

    /** One thread for every question, so an answer is never given while a
     *  check still holds the output the film is about to open. */
    private val worker = Executors.newSingleThreadExecutor { Thread(it, "sound-check").apply { isDaemon = true } }

    /** Check the output the box is on now, without waiting: one never checked,
     *  and again any format found silent, which can also be an output that was
     *  still waking up. */
    fun warm(context: Context) {
        val app = context.applicationContext
        worker.execute { answer(app, again = true) }
    }

    /** The most channels of each surround format that really start, by the
     *  check's name (ac3, eac3, dts, truehd). */
    fun heard(context: Context): Map<String, Int> {
        val app = context.applicationContext
        return try {
            worker.submit<Map<String, Int>> { answer(app, again = false) }.get(WAIT_MS, TimeUnit.MILLISECONDS)
        } catch (_: TimeoutException) {
            val claims = claimed(app)
            Log.e(TAG, "sound check still running after ${WAIT_MS}ms, answering with what the platform claims: $claims")
            claims
        }
    }

    /** What the check found for the output the box is on now, or null when it
     *  has not been checked: the engine asks on its own thread and must not
     *  wait for a check. */
    fun known(context: Context): Map<String, Int>? {
        val app = context.applicationContext
        return kept(app, signature(app, claimed(app)))
    }

    /** The check's name for an engine format, or null for one it does not check. */
    fun kindOf(mime: String?): String? = KIND_OF_MIME[mime]

    /** A box whose screen is off may not be sending anything over HDMI, and
     *  every format would be found silent and kept that way. */
    private fun answer(context: Context, again: Boolean): Map<String, Int> {
        val claims = claimed(context)
        if (!awake(context)) {
            Log.i(TAG, "screen is off, answering with what the platform claims: $claims")
            return claims
        }
        val signature = signature(context, claims)
        val kept = kept(context, signature)
        val silent = kept?.filter { (name, channels) -> channels == 0 && claims.getValue(name) > 0 }.orEmpty()
        if (kept != null && (!again || silent.isEmpty())) return kept
        return check(context, claims, kept).also { keep(context, signature, it) }
    }

    private fun awake(context: Context): Boolean =
        context.getSystemService(DisplayManager::class.java).getDisplay(Display.DEFAULT_DISPLAY)?.state == Display.STATE_ON

    /** A layout the output will not open is tried narrower; a format whose
     *  clock does not move is not tried again, since that is its decoder and
     *  not its channels. */
    private fun check(context: Context, claims: Map<String, Int>, kept: Map<String, Int>?): Map<String, Int> =
        claims.mapValues { (name, claim) ->
            kept?.get(name)?.takeIf { it > 0 }?.let { return@mapValues it }
            val kind = KINDS.getValue(name)
            val sample by lazy { context.resources.openRawResource(kind.sample).use { it.readBytes() } }
            for (channels in intArrayOf(8, 6, 2).filter { it <= minOf(claim, kind.most) }) {
                when (val outcome = starts(kind, channels, sample)) {
                    is Outcome.Started -> {
                        Log.i(TAG, "$name at $channels channels started in ${outcome.ms}ms")
                        return@mapValues channels
                    }
                    Outcome.Silent -> {
                        Log.w(TAG, "$name at $channels channels is claimed by the platform but does not start here")
                        return@mapValues 0
                    }
                    Outcome.Refused -> Log.w(TAG, "$name at $channels channels cannot be opened here")
                }
            }
            0
        }

    private fun starts(kind: Kind, channels: Int, sample: ByteArray): Outcome {
        val track = open(kind, channels) ?: return Outcome.Refused
        try {
            if (track.state != AudioTrack.STATE_INITIALIZED) return Outcome.Refused
            val began = SystemClock.elapsedRealtime()
            var at = 0
            var playing = false
            while (SystemClock.elapsedRealtime() - began < LISTEN_MS) {
                val left = sample.size - at
                val wrote = track.write(ByteBuffer.wrap(sample, at, left), left, AudioTrack.WRITE_NON_BLOCKING)
                if (wrote < 0) {
                    Log.w(TAG, "${kind.mime} write refused with $wrote")
                    return Outcome.Silent
                }
                at = (at + wrote) % sample.size
                if (!playing) {
                    track.play()
                    playing = true
                }
                if (track.playbackHeadPosition > 0) return Outcome.Started(SystemClock.elapsedRealtime() - began)
                if (wrote == 0) Thread.sleep(POLL_MS)
            }
            return Outcome.Silent
        } finally {
            track.release()
            Thread.sleep(SETTLE_MS)
        }
    }

    /** The HDMI output stays with a released track for a moment, and a format
     *  opened inside that moment is refused as if the box could not carry it. */
    private fun open(kind: Kind, channels: Int): AudioTrack? {
        val until = SystemClock.elapsedRealtime() + OPEN_MS
        while (true) {
            try {
                return AudioTrack.Builder()
                    .setAudioAttributes(Box.SOUND.platformAudioAttributes)
                    .setAudioFormat(
                        AudioFormat.Builder()
                            .setEncoding(kind.encoding)
                            .setSampleRate(48_000)
                            .setChannelMask(mask(channels))
                            .build(),
                    )
                    .setTransferMode(AudioTrack.MODE_STREAM)
                    .setBufferSizeInBytes(kind.buffer)
                    .build()
            } catch (_: UnsupportedOperationException) {
                if (SystemClock.elapsedRealtime() >= until) return null
                Thread.sleep(SETTLE_MS / 5)
            }
        }
    }

    private fun mask(channels: Int): Int = when {
        channels >= 8 -> AudioFormat.CHANNEL_OUT_7POINT1_SURROUND
        channels >= 6 -> AudioFormat.CHANNEL_OUT_5POINT1
        else -> AudioFormat.CHANNEL_OUT_STEREO
    }

    /** What the platform says each format can carry: the most channels it
     *  claims, the check's starting point and never exceeded. */
    private fun claimed(context: Context): Map<String, Int> {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return KINDS.mapValues { 0 }
        val able = AudioCapabilities.getCapabilities(context, Box.SOUND, null, emptyList())
        return KINDS.mapValues { (_, kind) ->
            intArrayOf(8, 6, 2).firstOrNull { channels ->
                val format = Format.Builder()
                    .setSampleMimeType(kind.mime)
                    .setChannelCount(channels)
                    .setSampleRate(48_000)
                    .build()
                able.isPassthroughPlaybackSupported(format, Box.SOUND)
            } ?: 0
        }
    }

    private fun signature(context: Context, claims: Map<String, Int>): String {
        val plug = context.registerReceiver(null, IntentFilter(AudioManager.ACTION_HDMI_AUDIO_PLUG))
        val settings = SETTINGS.map { Settings.Global.getString(context.contentResolver, it) }
        return listOf(
            METHOD,
            Build.FINGERPRINT,
            plug?.getIntExtra(AudioManager.EXTRA_AUDIO_PLUG_STATE, -1),
            plug?.getIntArrayExtra(AudioManager.EXTRA_ENCODINGS)?.sorted(),
            plug?.getIntExtra(AudioManager.EXTRA_MAX_CHANNEL_COUNT, -1),
            settings,
            claims.toSortedMap(),
        ).joinToString("|")
    }

    private fun kept(context: Context, signature: String): Map<String, Int>? {
        val all = stored(context)
        val one = all.optJSONObject(signature) ?: return null
        return KINDS.keys.associateWith { one.optInt(it, 0) }
    }

    /** Newest last; JSONObject keeps the order names were put in. */
    private fun keep(context: Context, signature: String, heard: Map<String, Int>) {
        val all = stored(context)
        all.remove(signature)
        all.put(signature, JSONObject(heard))
        while (all.length() > KEPT) all.remove(all.keys().next())
        context.getSharedPreferences(STORE, Context.MODE_PRIVATE).edit { putString(HEARD, all.toString()) }
    }

    private fun stored(context: Context): JSONObject =
        JSONObject(context.getSharedPreferences(STORE, Context.MODE_PRIVATE).getString(HEARD, null) ?: "{}")
}
