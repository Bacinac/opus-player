package biz.boskovic.opus.player

import android.content.Context
import android.os.Handler
import android.os.SystemClock
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.Renderer
import androidx.media3.exoplayer.audio.AudioOutput
import androidx.media3.exoplayer.audio.AudioOutputProvider
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.AudioTrackAudioOutputProvider
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.audio.ForwardingAudioOutputProvider
import androidx.media3.exoplayer.mediacodec.MediaCodecSelector
import androidx.media3.exoplayer.video.MediaCodecVideoRenderer
import androidx.media3.exoplayer.video.VideoRendererEventListener

/** The renderers ExoPlayer would build, with the picture's decoder chosen by
 *  [BaseLayer], the sound's AudioTrack handed over by [ReleasedFirst], and
 *  only the surround formats [SoundCheck] heard start passed through. */
@UnstableApi
internal class Renderers(private val context: Context) : DefaultRenderersFactory(context) {
    override fun buildVideoRenderers(
        context: Context,
        extensionRendererMode: Int,
        mediaCodecSelector: MediaCodecSelector,
        enableDecoderFallback: Boolean,
        eventHandler: Handler,
        eventListener: VideoRendererEventListener,
        allowedVideoJoiningTimeMs: Long,
        out: ArrayList<Renderer>,
    ) {
        super.buildVideoRenderers(
            context, extensionRendererMode, mediaCodecSelector, enableDecoderFallback,
            eventHandler, eventListener, allowedVideoJoiningTimeMs, out,
        )
        val at = out.indexOfFirst { it is MediaCodecVideoRenderer }
        check(at >= 0) { "no MediaCodec video renderer to replace" }
        out[at] = BaseLayer(
            this.context,
            MediaCodecVideoRenderer.Builder(context)
                .setMediaCodecSelector(mediaCodecSelector)
                .setAllowedJoiningTimeMs(allowedVideoJoiningTimeMs)
                .setEnableDecoderFallback(enableDecoderFallback)
                .setEventHandler(eventHandler)
                .setEventListener(eventListener)
                .setMaxDroppedFramesToNotify(DefaultRenderersFactory.MAX_DROPPED_VIDEO_FRAME_COUNT_TO_NOTIFY),
        )
    }

    override fun buildAudioSink(
        context: Context,
        enableFloatOutput: Boolean,
        enableAudioOutputPlaybackParams: Boolean,
    ): AudioSink = DefaultAudioSink.Builder(context)
        .setEnableFloatOutput(enableFloatOutput)
        .setEnableAudioOutputPlaybackParameters(enableAudioOutputPlaybackParams)
        .setAudioOutputProvider(
            Heard(ReleasedFirst(AudioTrackAudioOutputProvider.Builder(context).build()), SoundCheck.known(context)),
        )
        .build()
}

/** The engine asks the platform the same question the page used to, and would
 *  pick the TrueHD track a box cannot start all over again: refused here, it
 *  takes the decoder or another track instead. Null is an output never
 *  checked, where the platform's word is all there is. */
@UnstableApi
private class Heard(
    provider: AudioOutputProvider,
    private val heard: Map<String, Int>?,
) : ForwardingAudioOutputProvider(provider) {
    override fun getFormatSupport(config: AudioOutputProvider.FormatConfig): AudioOutputProvider.FormatSupport {
        val kind = SoundCheck.kindOf(config.format.sampleMimeType)
        if (heard != null && kind != null && (heard[kind] ?: 0) == 0) return AudioOutputProvider.FormatSupport.UNSUPPORTED
        return super.getFormatSupport(config)
    }
}

/** Every seek throws the sound's AudioTrack away and opens another. Media3
 *  releases the old one 20 ms later on a background thread and opens the new
 *  one at once, so a seek into what is already buffered opens it while the old
 *  one still holds the HDMI output. A passthrough track opened that way can
 *  start from the old one's position, and the picture then follows a clock
 *  the sound is not on until the next seek. ExoPlayer 2 waited for the
 *  release; this waits again. */
@UnstableApi
private class ReleasedFirst(provider: AudioOutputProvider) : ForwardingAudioOutputProvider(provider) {
    override fun getAudioOutput(config: AudioOutputProvider.OutputConfig): AudioOutput {
        val until = SystemClock.elapsedRealtime() + RELEASE_WAIT_MS
        while (hasPendingReleases() && SystemClock.elapsedRealtime() < until) Thread.sleep(RELEASE_POLL_MS)
        // DefaultAudioSink retries a refused output on its own once no release is pending
        if (hasPendingReleases()) {
            throw AudioOutputProvider.InitializationException(
                IllegalStateException("the previous AudioTrack is still being released after ${RELEASE_WAIT_MS}ms"),
            )
        }
        return super.getAudioOutput(config)
    }
}

private const val RELEASE_WAIT_MS = 1000L
private const val RELEASE_POLL_MS = 5L
