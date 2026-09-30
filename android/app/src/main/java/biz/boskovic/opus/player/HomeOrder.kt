package biz.boskovic.opus.player

import android.content.Context
import androidx.core.content.edit

/** The order of the television's doors: arranged on the launcher, followed by
 *  the OPUS Home row. */
internal object HomeOrder {
    const val CAMERAS = "opus:cameras"

    /** The deliberate launcher grid, visible to its contract test. */
    val PRIMARY = listOf(
        "biz.boskovic.opus.player",
        "com.uniqcast.uniqtv.eronet",
        "hr.a1.android.tv.xploretv",
        "com.netflix.ninja",
        "com.aspiro.tidal",
        "com.spotify.tv.android",
    )

    private const val PREFS = "opus_home"
    private const val ORDER = "app_order"

    fun items(context: Context): List<String> {
        val defaults = PRIMARY + CAMERAS
        val saved = prefs(context).getString(ORDER, "").orEmpty().split(',').filter { it in defaults }
        return (saved + defaults).distinct()
    }

    fun move(context: Context, key: String, by: Int): Boolean {
        val order = items(context).toMutableList()
        val from = order.indexOf(key)
        val to = (from + by).coerceIn(0, order.lastIndex)
        if (from < 0 || from == to) return false
        order.add(to, order.removeAt(from))
        prefs(context).edit { putString(ORDER, order.joinToString(",")) }
        return true
    }

    private fun prefs(context: Context) = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
