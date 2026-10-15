package biz.boskovic.opus.player

import android.content.Context
import android.media.MediaCodecInfo.CodecProfileLevel
import android.util.Log
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.CodecSpecificDataUtil
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.mediacodec.MediaCodecInfo
import androidx.media3.exoplayer.mediacodec.MediaCodecSelector
import androidx.media3.exoplayer.video.MediaCodecVideoRenderer

/** A Dolby Vision film the box's Dolby Vision decoder says it cannot take is
 *  played from its HDR10 base layer instead. The Shield's DOVI decoder declares
 *  profiles 4, 5, 8 and 9 but not 7 (a Blu-ray's dual layer); given one anyway,
 *  it drew a red line across the top of the frame and took seconds to stop.
 *  Media3 offers an HEVC decoder for the base layer of 4 and 8 only, so for 7
 *  one is asked for here: a Blu-ray's base layer is plain HDR10. A decoder that
 *  does support the file keeps it. */
@UnstableApi
internal class BaseLayer(
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
        val (vision, others) = all.partition { it.mimeType == MimeTypes.VIDEO_DOLBY_VISION }
        if (vision.any { it.isFormatSupported(context, format) }) return all
        val base = others.ifEmpty {
            if (CodecSpecificDataUtil.getCodecProfileAndLevel(format)?.first == CodecProfileLevel.DolbyVisionProfileDvheDtb) {
                mediaCodecSelector.getDecoderInfos(MimeTypes.VIDEO_H265, requiresSecureDecoder, false)
            } else {
                emptyList()
            }
        }
        if (base.isEmpty()) return all
        Log.i("OpusEngine", "Dolby Vision ${format.codecs} is not supported here; playing its base layer")
        return base
    }
}
