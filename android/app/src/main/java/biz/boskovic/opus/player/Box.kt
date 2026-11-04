package biz.boskovic.opus.player

import android.content.Context
import android.hardware.display.DisplayManager
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.MediaFormat
import android.media.MediaCodecList
import android.os.Build
import android.view.Display
import androidx.core.content.ContextCompat
import androidx.media3.common.AudioAttributes as Media3AudioAttributes
import androidx.media3.common.C
import org.json.JSONArray
import org.json.JSONObject

/** What this particular box can do, asked of it rather than assumed.
 *
 * The reason it exists: this one has no DTS decoder and no AC3 decoder, so a
 * film whose only sound is DTS plays as a silent picture if it is handed over
 * untouched. The server can repackage that — copying the picture and turning
 * only the sound into something the box owns — but it has to be told, and the
 * only honest source for what the box owns is the box. */
object Box {

    /** How the engine plays and how the amplifier is asked about it: the same
     *  words on both sides, or the answer is to a different question. */
    val SOUND: Media3AudioAttributes = Media3AudioAttributes.Builder()
        .setUsage(C.USAGE_MEDIA)
        .setContentType(C.AUDIO_CONTENT_TYPE_MOVIE)
        .build()

    /** The manufacturer id of the EDID the kernel makes up when it can read none. */
    private const val STAND_IN = "LNX"

    /** ffprobe's names for a codec on one side, Android's on the other. */
    private val MIME = mapOf(
        "aac" to "audio/mp4a-latm",
        "mp3" to "audio/mpeg",
        "flac" to "audio/flac",
        "opus" to "audio/opus",
        "vorbis" to "audio/vorbis",
        "ac3" to "audio/ac3",
        "eac3" to "audio/eac3",
        "dts" to "audio/vnd.dts",
        "dca" to "audio/vnd.dts",
        "truehd" to "audio/vnd.dolby.mlp",
    )

    /** The catalogue's names for pictures, translated before asking the
     * platform. A native engine must not be handed a codec merely because an
     * Android box exists: that used to turn an unsupported film into a black
     * screen while the server believed direct play had succeeded. */
    private val VIDEO_MIME = mapOf(
        "h264" to "video/avc",
        "hevc" to "video/hevc",
        "av1" to "video/av01",
        "vp9" to "video/x-vnd.on2.vp9",
        "mpeg2video" to "video/mpeg2",
        "mpeg4" to "video/mp4v-es",
        "h263" to "video/3gpp",
        "vc1" to "video/wvc1",
    )

    /** ffprobe's second name for DTS, where the sound check knows only one. */
    private val SAME = mapOf("dca" to "dts")

    fun describe(context: Context): String {
        val size = displaySize(context)
        val heard = SoundCheck.heard(context)
        val widest = MIME.keys.associateWith { heard[SAME[it] ?: it] ?: 0 }.filterValues { it > 0 }
        return JSONObject()
            .put("w", size.first)
            .put("h", size.second)
            .put("audio", JSONArray(MIME.keys.filter { decodes(it) || it in widest }))
            .put("widest", JSONObject(widest))
            .put("channels", channels(context))
            .toString()
    }

    /** What the picture goes into, as that device names itself over HDMI: the
     * box behind the receiver is plugged into the receiver, and the same box
     * carried to a bare panel is plugged into the panel. Empty where Android
     * cannot say: asleep, the box reads the kernel's stand-in (LNX, "Linux
     * FHD") in place of whatever it is plugged into. */
    fun plugged(context: Context): String {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) return ""
        val display = context.getSystemService(DisplayManager::class.java)
            .getDisplay(Display.DEFAULT_DISPLAY) ?: return ""
        val sink = display.deviceProductInfo ?: return ""
        if (display.state != Display.STATE_ON || sink.manufacturerPnpId == STAND_IN) return ""
        return listOfNotNull(sink.name, "${sink.manufacturerPnpId} ${sink.productId}").joinToString(" · ")
    }

    /** Whether this box has a hardware decoder for this exact picture shape.
     *
     * API 28 has no reliable way to distinguish a hardware decoder from a
     * software one. Treat it as unavailable so the server makes the supported
     * H.264 stream instead of quietly consuming the TV's CPU. */
    fun hardwareDecodesVideo(codec: String, width: Int, height: Int): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return false
        val mime = VIDEO_MIME[codec.lowercase()] ?: return false
        val format = MediaFormat.createVideoFormat(mime, width.coerceAtLeast(2), height.coerceAtLeast(2))
        return MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos.any { info ->
            if (info.isEncoder || !info.isHardwareAccelerated ||
                info.supportedTypes.none { it.equals(mime, ignoreCase = true) }) return@any false
            try {
                info.getCapabilitiesForType(mime).isFormatSupported(format)
            } catch (_: IllegalArgumentException) {
                false
            }
        }
    }

    /** How many channels can actually leave this box, asked of the output rather
     * than guessed from the codec list. A television wired to an amplifier takes
     * eight; the same box on a bare panel takes two, and sending it six is how a
     * centre channel goes missing. */
    private fun channels(context: Context): Int {
        val audio = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val out = audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            .filter {
                it.type == AudioDeviceInfo.TYPE_HDMI ||
                    it.type == AudioDeviceInfo.TYPE_HDMI_ARC ||
                    it.type == AudioDeviceInfo.TYPE_AUX_LINE
            }
        val most = out.flatMap { it.channelCounts.toList() }.maxOrNull() ?: 0
        return if (most > 0) most else 2
    }

    private fun decodes(codec: String): Boolean {
        val mime = MIME[codec] ?: return false
        return MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos.any { info ->
            !info.isEncoder && info.supportedTypes.any { it.equals(mime, ignoreCase = true) }
        }
    }

    /** The panel the picture ends up on, in real pixels: the box draws its own
     * interface at 1080p, so the window would understate a 4K screen. */
    private fun displaySize(context: Context): Pair<Int, Int> {
        val display = ContextCompat.getDisplayOrDefault(context)
        val mode = display.supportedModes.maxByOrNull { it.physicalWidth * it.physicalHeight } ?: display.mode
        return Pair(mode.physicalWidth, mode.physicalHeight)
    }
}
