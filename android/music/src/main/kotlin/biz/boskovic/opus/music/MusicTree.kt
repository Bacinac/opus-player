package biz.boskovic.opus.music

import android.content.Context
import android.net.Uri
import androidx.annotation.OptIn
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.util.UnstableApi
import biz.boskovic.opus.core.Opus
import biz.boskovic.opus.core.OpusHttp
import java.text.Normalizer
import java.util.Locale
import org.json.JSONArray
import org.json.JSONObject

/** The Player's shelf as a browse tree: root → artists → letter → artist →
 *  record → songs, and root → radio → station. */
@OptIn(UnstableApi::class)
object MusicTree {
    private const val ROOT = "root"
    const val CONTINUE = "continue"
    private const val RECENT = "recent"
    private const val FAVORITES = "favorites"
    private const val OFFLINE = "offline"
    private const val ARTISTS = "artists"
    private const val RADIO = "radio"
    private const val LETTER = "letter:"
    private const val ARTIST = "artist:"
    private const val RELEASE = "release:"
    private const val OFFLINE_RELEASE = "offline-release:"
    private const val TRACK = "track:"
    private const val STATION = "station:"
    private const val LIFETIME_MS = 6 * 60 * 60 * 1000L

    private val CROATIAN = Locale.forLanguageTag("hr")
    private val LETTERS = "abcčćdđefghijklmnopqrsštuvwxyzž".toSet()
    private val DIGRAPHS = setOf("dž", "lj", "nj")
    private val NUMBERS = setOf(CharCategory.DECIMAL_DIGIT_NUMBER, CharCategory.LETTER_NUMBER, CharCategory.OTHER_NUMBER)

    private val playable = Recent<String, MediaItem>(2_000, LIFETIME_MS)
    private val recordOf = Recent<String, String>(2_000, LIFETIME_MS)
    private val recordSongs = Recent<String, List<MediaItem>>(100, LIFETIME_MS)
    private val searches = Recent<String, List<MediaItem>>(20, LIFETIME_MS)
    private val shelf = Recent<Unit, Map<String, List<MediaItem>>>(1, LIFETIME_MS)

    /** Nothing browsed under one pairing is shown under the next, or after a refusal. */
    fun forget() {
        playable.clear()
        recordOf.clear()
        recordSongs.clear()
        searches.clear()
        shelf.clear()
    }

    fun root(context: Context): MediaItem = folder(ROOT, "OPUS Music", MediaMetadata.MEDIA_TYPE_FOLDER_MIXED)

    fun continuation(context: Context): MediaItem? = try {
        Kept.restore(context)?.let {
            MediaItem.Builder()
                .setMediaId(CONTINUE)
                .setMediaMetadata(
                    MediaMetadata.Builder()
                        .setTitle(context.getString(R.string.lib_continue))
                        .setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC)
                        .setIsBrowsable(false)
                        .setIsPlayable(true)
                        .build()
                )
                .build()
        }
    } catch (_: org.json.JSONException) {
        // The service will discard the malformed saved queue when playback is
        // requested. It must not make the whole Auto browse root unavailable.
        null
    }

    private fun recent(context: Context): List<MediaItem> = try {
        Kept.recent(context)
    } catch (_: org.json.JSONException) {
        Kept.drop(context)
        emptyList()
    }

    suspend fun children(context: Context, parentId: String): List<MediaItem> {
        Car.ensurePaired(context)
        return when {
            parentId == ROOT -> buildList {
                continuation(context)?.let(::add)
                if (recent(context).isNotEmpty()) {
                    add(folder(RECENT, context.getString(R.string.lib_recent), MediaMetadata.MEDIA_TYPE_FOLDER_MIXED))
                }
                if (favorites(context).isNotEmpty()) {
                    add(folder(FAVORITES, context.getString(R.string.lib_favorites), MediaMetadata.MEDIA_TYPE_FOLDER_MIXED))
                }
                if (OfflineAlbums.all(context).isNotEmpty()) {
                    add(folder(OFFLINE, context.getString(R.string.lib_offline), MediaMetadata.MEDIA_TYPE_FOLDER_ALBUMS))
                }
                add(folder(ARTISTS, context.getString(R.string.lib_artists), MediaMetadata.MEDIA_TYPE_FOLDER_ARTISTS))
                add(folder(RADIO, context.getString(R.string.lib_radio), MediaMetadata.MEDIA_TYPE_FOLDER_RADIO_STATIONS))
            }
            parentId == ARTISTS -> letters(context)
            parentId == RECENT -> recent(context).onEach { playable[it.mediaId] = it }
            parentId == FAVORITES -> favorites(context)
            parentId == OFFLINE -> offlineAlbums(context)
            parentId == RADIO -> stations(context)
            parentId.startsWith(LETTER) -> (shelf[Unit] ?: artists(context))[parentId.removePrefix(LETTER)].orEmpty()
            parentId.startsWith(ARTIST) -> records(context, parentId.removePrefix(ARTIST))
            parentId.startsWith(RELEASE) -> songs(context, parentId)
            parentId.startsWith(OFFLINE_RELEASE) -> offlineSongs(context, parentId)
            else -> throw IllegalArgumentException("no such folder: $parentId")
        }
    }

    private suspend fun letters(context: Context): List<MediaItem> =
        artists(context).map { (letter, _) -> folder(LETTER + letter, letter, MediaMetadata.MEDIA_TYPE_FOLDER_ARTISTS) }

    private suspend fun artists(context: Context): Map<String, List<MediaItem>> {
        val list = JSONArray(OpusHttp.get(Car.client(context), "/api/library/music?order=title"))
        val grouped = LinkedHashMap<String, MutableList<MediaItem>>()
        for (i in 0 until list.length()) {
            val artist = list.getJSONObject(i)
            val title = artist.getString("title")
            val held = artist.optInt("held")
            grouped.getOrPut(initial(title)) { mutableListOf() } += folder(
                ARTIST + artist.getInt("id"), title, MediaMetadata.MEDIA_TYPE_ARTIST,
                subtitle = if (held > 0) context.resources.getQuantityString(R.plurals.artist_held, held, held) else null,
                art = art(artist.optString("image")),
            )
        }
        shelf[Unit] = grouped
        return grouped
    }

    /** The letter a name files under, by the rule of `initialOf` in opus-ui's
     *  letters.ts, so the car's folders are the rail's letters. */
    internal fun initial(title: String): String {
        val text = Normalizer.normalize(title.trim(), Normalizer.Form.NFC)
        val first = text.firstOrNull() ?: return "#"
        if (first in '0'..'9') return "#"
        val lowered = text.take(2).lowercase(CROATIAN)
        if (lowered in DIGRAPHS) return lowered[0].uppercase(CROATIAN) + lowered[1]
        val letter = lowered[0]
        if (letter in LETTERS) return letter.uppercase(CROATIAN)
        val stripped = Normalizer.normalize(letter.toString(), Normalizer.Form.NFD)[0]
        if (stripped in LETTERS) return stripped.uppercase(CROATIAN)
        return if (letter.isLetter() || letter.category in NUMBERS) "?" else "#"
    }

    private suspend fun records(context: Context, artistId: String): List<MediaItem> {
        val releases = JSONObject(OpusHttp.get(Car.client(context), "/api/library/artist/$artistId"))
            .getJSONArray("releases")
        return (0 until releases.length()).map { i ->
            val release = releases.getJSONObject(i)
            folder(
                RELEASE + release.getInt("id"), release.getString("title"), MediaMetadata.MEDIA_TYPE_ALBUM,
                subtitle = release.optString("year").ifEmpty { null },
                art = art(release.optString("cover")),
            )
        }
    }

    private suspend fun songs(context: Context, recordId: String): List<MediaItem> {
        val tracks = JSONObject(OpusHttp.get(Car.client(context), "/api/library/release/${recordId.removePrefix(RELEASE)}"))
            .getJSONArray("tracks")
        val items = (0 until tracks.length()).map { i ->
            val track = tracks.getJSONObject(i)
            song(track, track.optString("cover_url"), Car.savesData(context)).also { recordOf[it.mediaId] = recordId }
        }
        recordSongs[recordId] = items
        return items
    }

    private fun offlineAlbums(context: Context): List<MediaItem> = OfflineAlbums.all(context).map { album ->
        folder(
            OFFLINE_RELEASE + album.id,
            album.title,
            MediaMetadata.MEDIA_TYPE_ALBUM,
            subtitle = album.artist.ifEmpty { null },
        )
    }

    private fun offlineSongs(context: Context, recordId: String): List<MediaItem> {
        val album = OfflineAlbums.find(context, recordId.removePrefix(OFFLINE_RELEASE).toLong())
            ?: throw IllegalArgumentException("no such offline album: $recordId")
        album.tracks.forEach { playable[it.mediaId] = it; recordOf[it.mediaId] = recordId }
        recordSongs[recordId] = album.tracks
        return album.tracks
    }

    private suspend fun stations(context: Context): List<MediaItem> {
        val list = JSONObject(OpusHttp.get(Car.client(context), "/api/radio/stations")).getJSONArray("stations")
        return (0 until list.length()).map { station(list.getJSONObject(it)) }
    }

    /** Account-scoped favourites come from Player; Library still owns every
     * track's current title and availability. Unplayable old entries stay
     * saved on the server, but never turn into a dead item on the dashboard. */
    private suspend fun favorites(context: Context): List<MediaItem> = try {
        val tracks = JSONObject(OpusHttp.get(Car.client(context), "/api/music/favorites"))
            .getJSONArray("tracks")
        rememberFavorites(context, (0 until tracks.length()).map(tracks::getJSONObject))
    } catch (offline: java.io.IOException) {
        // A browse request must not hide music that the person deliberately
        // saved before leaving coverage. A real authorization refusal clears
        // Kept through Car before it reaches this fallback.
        savedFavorites(context).ifEmpty { throw offline }
    }

    /** Store only a last verified, pairing-scoped view of favourites. The
     * stream URI is retained exactly, so cached MP3/Opus songs stay cacheable. */
    internal fun rememberFavorites(context: Context, tracks: List<JSONObject>): List<MediaItem> =
        tracks.mapNotNull { track ->
            if (!track.optBoolean("playable", true)) null
            else song(track, track.optString("cover_url"), Car.savesData(context))
        }.also { Kept.keepFavorites(context, it) }

    private fun savedFavorites(context: Context): List<MediaItem> = try {
        Kept.favorites(context).onEach { playable[it.mediaId] = it }
    } catch (_: org.json.JSONException) {
        // The list is a cache, never a reason to lose the saved playback queue.
        Kept.keepFavorites(context, emptyList())
        emptyList()
    }

    private fun station(card: JSONObject): MediaItem {
        val item = MediaItem.Builder()
            .setMediaId(STATION + card.getInt("id"))
            .setUri(Opus.url(card.getString("play_url")))
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setTitle(card.getString("title"))
                    .setSubtitle(card.optString("subtitle").ifEmpty { null })
                    .setArtworkUri(art(card.optString("image")))
                    .setMediaType(MediaMetadata.MEDIA_TYPE_RADIO_STATION)
                    .setIsBrowsable(false)
                    .setIsPlayable(true)
                    .build()
            )
            .build()
        playable[item.mediaId] = item
        return item
    }

    suspend fun search(context: Context, query: String): List<MediaItem> {
        Car.ensurePaired(context)
        val words = query.trim()
        if (words.isEmpty()) return emptyList()
        val found = JSONArray(OpusHttp.get(Car.client(context), "/api/library/search?q=${Uri.encode(words)}"))
        return (0 until found.length()).map { i ->
            val card = found.getJSONObject(i)
            song(card, card.optString("image"), Car.savesData(context))
        }.also { searches[query] = it }
    }

    suspend fun searched(context: Context, query: String): List<MediaItem> =
        searches[query] ?: search(context, query)

    internal fun song(track: JSONObject, cover: String, compact: Boolean = false): MediaItem {
        val item = MediaItem.Builder()
            .setMediaId(TRACK + track.getLong("id"))
            .setUri(stream(track.getLong("id"), track.optString("codec"), compact))
            .setMediaMetadata(
                MediaMetadata.Builder()
                    .setTitle(track.optString("title").ifEmpty { null })
                    .setArtist(track.optString("artist").ifEmpty { null })
                    .setAlbumTitle(track.optString("album").ifEmpty { null })
                    .setTrackNumber(if (track.isNull("position")) null else track.optInt("position"))
                    .setDurationMs(if (track.isNull("duration_s")) null else (track.optDouble("duration_s") * 1000).toLong())
                    .setArtworkUri(art(cover))
                    .setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC)
                    .setIsBrowsable(false)
                    .setIsPlayable(true)
                    .build()
            )
            .build()
        playable[item.mediaId] = item
        return item
    }

    /** One canonical address for playing and prefetching a track. The cache
     * key includes this complete URL, so the requested edition must agree. */
    internal fun stream(id: Long, codec: String, compact: Boolean = false): String {
        val format = if (compact) "opus" else codec.ifEmpty { "flac" }
        val compactFlag = if (compact) "&compact=1" else ""
        return Opus.url("/api/play/track/$id/stream?fmt=.$format$compactFlag")
    }

    /** The item a controller can play, from the browse cache or, after the
     *  process has been restarted, rebuilt from its id. */
    suspend fun playable(context: Context, mediaId: String): MediaItem {
        playable[mediaId]?.let { return it }
        Car.ensurePaired(context)
        OfflineAlbums.track(context, mediaId)?.let {
            playable[it.mediaId] = it
            return it
        }
        return when {
            mediaId == CONTINUE -> continuation(context)
                ?: throw IllegalArgumentException("nothing has been played yet")
            mediaId.startsWith(TRACK) -> MediaItem.Builder()
                .setMediaId(mediaId)
                .setUri(stream(mediaId.removePrefix(TRACK).toLong(), "", Car.savesData(context)))
                .build()
            mediaId.startsWith(STATION) -> station(
                JSONObject(OpusHttp.get(Car.client(context), "/api/radio/stations/${mediaId.removePrefix(STATION)}"))
            )
            else -> throw IllegalArgumentException("not playable: $mediaId")
        }
    }

    /** A tapped song brings its whole record as the queue. */
    suspend fun queueFrom(context: Context, mediaId: String): Pair<List<MediaItem>, Int> {
        val record = recordOf[mediaId]?.let { recordSongs[it] }
            ?: return listOf(playable(context, mediaId)) to 0
        return record to record.indexOfFirst { it.mediaId == mediaId }.coerceAtLeast(0)
    }

    private fun art(url: String): Uri? {
        if (url.isEmpty() || url == "null") return null
        return Opus.url("/api/art?u=${Uri.encode(url)}&w=640").toUri()
    }

    private fun folder(
        id: String,
        title: String,
        mediaType: Int,
        subtitle: String? = null,
        art: Uri? = null,
    ): MediaItem = MediaItem.Builder()
        .setMediaId(id)
        .setMediaMetadata(
            MediaMetadata.Builder()
                .setTitle(title)
                .setSubtitle(subtitle)
                .setArtworkUri(art)
                .setMediaType(mediaType)
                .setIsBrowsable(true)
                .setIsPlayable(false)
                .build()
        )
        .build()
}
