package biz.boskovic.opus.music

import android.content.Context
import androidx.annotation.OptIn
import androidx.core.content.edit
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.util.UnstableApi
import biz.boskovic.opus.core.OpusHttp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** Albums a person explicitly chose for offline use.
 *
 * The saved stream address and metadata make the selected library browsable
 * without a catalogue request. The backing preferences are deliberately the
 * same pairing-scoped store as [Kept], so signing out removes both the list and
 * all cached audio for the prior person.
 */
@OptIn(UnstableApi::class)
object OfflineAlbums {
    private const val FILE = "opus_queue"
    private const val ALBUMS = "offline_albums"

    data class Album(val id: Long, val title: String, val artist: String, val tracks: List<MediaItem>)

    private fun prefs(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)

    fun all(context: Context): List<Album> {
        val saved = JSONArray(prefs(context).getString(ALBUMS, "[]"))
        return (0 until saved.length()).map { at -> opened(saved.getJSONObject(at)) }
    }

    fun find(context: Context, id: Long): Album? = all(context).firstOrNull { it.id == id }

    fun track(context: Context, mediaId: String): MediaItem? =
        all(context).asSequence().flatMap { it.tracks.asSequence() }.firstOrNull { it.mediaId == mediaId }

    /** Read the release once while connected; downloading later uses this
     * stored immutable track list and never guesses a different edition. */
    suspend fun add(context: Context, id: Long, title: String, artist: String): Album =
        withContext(Dispatchers.IO) {
            val release = JSONObject(OpusHttp.get(Car.client(context), "/api/library/release/$id"))
            val found = release.getJSONArray("tracks")
            val tracks = (0 until found.length()).map { at ->
                val track = found.getJSONObject(at)
                MusicTree.song(track, track.optString("cover_url"), Car.savesData(context))
            }
            Album(id, title, artist, tracks).also { album -> replace(context, album) }
        }

    fun remove(context: Context, id: Long) {
        val kept = all(context).filterNot { it.id == id }
        save(context, kept)
    }

    private fun replace(context: Context, album: Album) =
        save(context, all(context).filterNot { it.id == album.id } + album)

    private fun save(context: Context, albums: List<Album>) {
        val packed = JSONArray()
        albums.forEach { packed.put(pack(it)) }
        prefs(context).edit { putString(ALBUMS, packed.toString()) }
    }

    private fun pack(album: Album): JSONObject = JSONObject()
        .put("id", album.id)
        .put("title", album.title)
        .put("artist", album.artist)
        .put("tracks", JSONArray().also { tracks -> album.tracks.forEach { tracks.put(pack(it)) } })

    private fun pack(item: MediaItem): JSONObject {
        val uri = item.localConfiguration?.uri ?: throw IllegalArgumentException("offline track has no stream URI")
        val meta = item.mediaMetadata
        return JSONObject()
            .put("id", item.mediaId)
            .put("uri", uri.toString())
            .put("title", meta.title?.toString())
            .put("artist", meta.artist?.toString())
            .put("album", meta.albumTitle?.toString())
            .put("art", meta.artworkUri?.toString())
            .put("duration", meta.durationMs)
            .put("position", meta.trackNumber)
    }

    private fun opened(saved: JSONObject): Album {
        val tracks = saved.getJSONArray("tracks")
        return Album(
            id = saved.getLong("id"),
            title = saved.getString("title"),
            artist = saved.optString("artist"),
            tracks = (0 until tracks.length()).map { at -> openedTrack(tracks.getJSONObject(at)) },
        )
    }

    private fun openedTrack(item: JSONObject): MediaItem = MediaItem.Builder()
        .setMediaId(item.getString("id"))
        .setUri(item.getString("uri"))
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(item.optString("title").ifEmpty { null })
                .setArtist(item.optString("artist").ifEmpty { null })
                .setAlbumTitle(item.optString("album").ifEmpty { null })
                .setArtworkUri(item.optString("art").ifEmpty { null }?.toUri())
                .setDurationMs(if (item.isNull("duration")) null else item.getLong("duration"))
                .setTrackNumber(if (item.isNull("position")) null else item.getInt("position"))
                .setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC)
                .setIsBrowsable(false)
                .setIsPlayable(true)
                .build(),
        )
        .build()
}
