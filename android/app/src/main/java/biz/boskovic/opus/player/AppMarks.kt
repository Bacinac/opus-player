package biz.boskovic.opus.player

import android.content.Context
import java.io.InputStream

/** The one set of application marks, in this APK's assets as `apps/<key>.png`,
 * keyed by package name (and `cameras` for the wall).
 *
 * Every file is the finished tile art: 16:9, transparent, the logo already
 * fitted into the same centred margin, so the Home launcher draws them as they
 * are. */
internal object AppMarks {
    const val CAMERAS = "cameras"

    fun open(context: Context, key: String): InputStream = context.assets.open("apps/$key.png")
}
