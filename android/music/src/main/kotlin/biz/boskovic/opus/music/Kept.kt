package biz.boskovic.opus.music

import android.content.Context
import androidx.core.net.toUri
import androidx.annotation.OptIn
import androidx.core.content.edit
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaSession
import org.json.JSONArray
import org.json.JSONObject

/** What was playing, kept so a restarted process can be resumed from Android
 *  Auto or the system's media controls. */
@OptIn(UnstableApi::class)
object Kept {
    private const val FILE = "opus_queue"
    private const val RECENT = "recent"
    private const val FAVORITES = "favorites"
    private const val RECENT_LIMIT = 20

    private fun packed(item: MediaItem): JSONObject {
        val uri = item.localConfiguration?.uri ?: return JSONObject()
        val meta = item.mediaMetadata
        return JSONObject()
            .put("id", item.mediaId)
            .put("uri", uri.toString())
            .put("title", meta.title?.toString())
            .put("artist", meta.artist?.toString())
            .put("album", meta.albumTitle?.toString())
            .put("art", meta.artworkUri?.toString())
            .put("duration", meta.durationMs)
            .put("type", meta.mediaType)
    }

    private fun opened(item: JSONObject): MediaItem = MediaItem.Builder()
        .setMediaId(item.getString("id"))
        .setUri(item.getString("uri"))
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(item.optString("title").ifEmpty { null })
                .setArtist(item.optString("artist").ifEmpty { null })
                .setAlbumTitle(item.optString("album").ifEmpty { null })
                .setArtworkUri(item.optString("art").ifEmpty { null }?.toUri())
                .setDurationMs(if (item.isNull("duration")) null else item.getLong("duration"))
                .setMediaType(if (item.isNull("type")) null else item.getInt("type"))
                .setIsBrowsable(false)
                .setIsPlayable(true)
                .build()
        )
        .build()

    fun save(context: Context, player: Player) {
        val items = JSONArray()
        for (i in 0 until player.mediaItemCount) {
            val item = player.getMediaItemAt(i)
            packed(item).takeIf { it.has("uri") }?.let(items::put)
        }
        val live = player.isCurrentMediaItemLive || player.duration == C.TIME_UNSET
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit {
            putString("items", items.toString())
            putInt("index", player.currentMediaItemIndex)
            putLong("position", if (live) 0L else player.currentPosition)
        }
    }

    fun drop(context: Context) {
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit { clear() }
    }

    /** A small, pairing-scoped listening history for the car's browse root. */
    fun remember(context: Context, item: MediaItem) {
        val next = packed(item)
        if (!next.has("uri")) return
        val prefs = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val before = JSONArray(prefs.getString(RECENT, "[]"))
        val items = JSONArray().put(next)
        for (i in 0 until before.length()) {
            val old = before.getJSONObject(i)
            if (old.optString("id") != item.mediaId && items.length() < RECENT_LIMIT) items.put(old)
        }
        prefs.edit { putString(RECENT, items.toString()) }
    }

    fun recent(context: Context): List<MediaItem> {
        val prefs = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val items = JSONArray(prefs.getString(RECENT, "[]"))
        return (0 until items.length()).map { opened(items.getJSONObject(it)) }
    }

    /** The last verified favourites are enough to enter the music cached by
     * the explicit offline action when the road has no signal. They are wiped
     * with the queue whenever this pairing ends. */
    fun keepFavorites(context: Context, items: List<MediaItem>) {
        val packed = JSONArray()
        for (item in items) packed(item).takeIf { it.has("uri") }?.let(packed::put)
        context.getSharedPreferences(FILE, Context.MODE_PRIVATE).edit {
            putString(FAVORITES, packed.toString())
        }
    }

    fun favorites(context: Context): List<MediaItem> {
        val prefs = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val items = JSONArray(prefs.getString(FAVORITES, "[]"))
        return (0 until items.length()).map { opened(items.getJSONObject(it)) }
    }

    fun restore(context: Context): MediaSession.MediaItemsWithStartPosition? {
        val kept = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
        val items = JSONArray(kept.getString("items", null) ?: return null)
        if (items.length() == 0) return null
        val restored = (0 until items.length()).map { opened(items.getJSONObject(it)) }
        val index = kept.getInt("index", 0).coerceIn(0, restored.lastIndex)
        return MediaSession.MediaItemsWithStartPosition(restored, index, kept.getLong("position", 0L))
    }
}
