package biz.boskovic.opus.player

import android.content.Context
import android.os.Handler
import android.util.Log
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.Renderer
import androidx.media3.exoplayer.mediacodec.MediaCodecInfo
import androidx.media3.exoplayer.mediacodec.MediaCodecSelector
import androidx.media3.exoplayer.video.MediaCodecVideoRenderer
import androidx.media3.exoplayer.video.VideoRendererEventListener

/** A Dolby Vision film the box's Dolby Vision decoder says it cannot take is
 *  played from its HDR10 base layer instead. The Shield's DOVI decoder refuses
 *  profile 7 (a Blu-ray's dual layer) and ExoPlayer used it anyway, having no
 *  better-supported choice by its own ranking; what came out carried a red line
 *  across the top of the frame. A decoder that does support the file keeps it. */
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
}

@UnstableApi
private class BaseLayer(
    private val context: Context,
    builder: MediaCodecVideoRenderer.Builder,
) : MediaCodecVideoRenderer(builder) {
    override fun getDecoderInfos(
        mediaCodecSelector: MediaCodecSelector,
        format: Format,
        requiresSecureDecoder: Boolean,
    ): List<MediaCodecInfo> {
        val all = super.getDecoderInfos(mediaCodecSelector, format, requiresSecureDecoder)
        if (format.sampleMimeType != MimeTypes.VIDEO_DOLBY_VISION) return all
        val (vision, base) = all.partition { it.mimeType == MimeTypes.VIDEO_DOLBY_VISION }
        if (base.isEmpty() || vision.any { it.isFormatSupported(context, format) }) return all
        Log.i("OpusEngine", "Dolby Vision ${format.codecs} is not supported here; playing its base layer")
        return base
    }
}
