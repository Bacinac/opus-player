package biz.boskovic.opus.music

import android.content.Context
import androidx.annotation.OptIn
import androidx.core.net.toUri
import androidx.media3.common.C
import androidx.media3.common.util.UnstableApi
import androidx.media3.database.StandaloneDatabaseProvider
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.cache.CacheDataSource
import androidx.media3.datasource.cache.CacheKeyFactory
import androidx.media3.datasource.cache.ContentMetadata
import androidx.media3.datasource.cache.LeastRecentlyUsedCacheEvictor
import androidx.media3.datasource.cache.SimpleCache
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.media3.datasource.okhttp.OkHttpDataSource
import biz.boskovic.opus.core.OpusHttp
import org.json.JSONObject

/** A bounded replay cache, not an offline library.
 *
 * Music already heard can survive a short signal loss or be replayed without
 * fetching it again.  The files remain in the OS cache area and are evicted at
 * 512 MiB. A cache key carries the non-secret pairing scope, and every pairing
 * change deletes every span, so audio fetched by one account cannot be played
 * by the next person using this phone.
 */
@OptIn(UnstableApi::class)
object ListeningCache {
    private const val MAX_BYTES = 512L * 1024 * 1024

    fun capacityBytes(): Long = MAX_BYTES

    @Volatile private var held: SimpleCache? = null

    private fun cache(context: Context): SimpleCache = held ?: synchronized(this) {
        held ?: SimpleCache(
            File(context.applicationContext.cacheDir, "opus-music"),
            LeastRecentlyUsedCacheEvictor(MAX_BYTES),
            StandaloneDatabaseProvider(context.applicationContext),
        ).also { held = it }
    }

    fun source(context: Context, upstream: DataSource.Factory): DataSource.Factory =
        CacheDataSource.Factory()
            .setCache(cache(context))
            .setUpstreamDataSourceFactory(upstream)
            // A full or damaged cache must never make playback unavailable.
            .setFlags(CacheDataSource.FLAG_IGNORE_CACHE_ON_ERROR)
            .setCacheKeyFactory(CacheKeyFactory { data -> cacheKey(context, data.uri.toString()) })

    private fun cacheKey(context: Context, address: String): String =
        "${Car.cacheScope(context)}:${address.toUri()}"

    /** Called when a pairing ends, is refused or is replaced. */
    fun clear(context: Context) {
        val current = cache(context)
        for (key in current.keys) current.removeResource(key)
    }

    fun usedBytes(context: Context): Long = cache(context).cacheSpace

    /** Explicitly keep the person's favourites for offline replay. This is
     * never automatic: a driver decides when their connection and allowance
     * can pay for it. */
    suspend fun cacheFavorites(
        context: Context,
        progress: suspend (done: Int, total: Int) -> Unit,
    ): Int =
        withContext(Dispatchers.IO) {
            val found = JSONObject(OpusHttp.get(Car.client(context), "/api/music/favorites"))
                .getJSONArray("tracks")
            val tracks = MusicTree.rememberFavorites(context, (0 until found.length()).map(found::getJSONObject))
            cacheItems(context, tracks, progress)
        }

    /** Save the tracks from albums chosen in the phone UI. Album membership is
     * recorded before this action, so an offline save cannot silently change
     * to a newer or differently encoded catalogue result. */
    suspend fun cacheAlbums(
        context: Context,
        progress: suspend (done: Int, total: Int) -> Unit,
    ): Int = withContext(Dispatchers.IO) {
        val unique = LinkedHashMap<String, androidx.media3.common.MediaItem>()
        OfflineAlbums.all(context).forEach { album ->
            album.tracks.forEach { unique.putIfAbsent(it.mediaId, it) }
        }
        cacheItems(context, unique.values.toList(), progress)
    }

    private suspend fun cacheItems(
        context: Context,
        tracks: List<androidx.media3.common.MediaItem>,
        progress: suspend (done: Int, total: Int) -> Unit,
    ): Int =
        withContext(Dispatchers.IO) {
            val factory = source(context, OkHttpDataSource.Factory(Car.client(context)))
            val fetched = mutableListOf<String>()
            var completed = 0
            withContext(Dispatchers.Main.immediate) { progress(completed, tracks.size) }
            for (track in tracks) {
                val address = track.localConfiguration?.uri?.toString() ?: continue
                val data = factory.createDataSource()
                try {
                    data.open(DataSpec(address.toUri()))
                    val buffer = ByteArray(64 * 1024)
                    while (true) {
                        if (data.read(buffer, 0, buffer.size) < 0) break
                    }
                    fetched += cacheKey(context, address)
                    completed += 1
                    withContext(Dispatchers.Main.immediate) { progress(completed, tracks.size) }
                } finally {
                    data.close()
                }
            }
            // The LRU can evict an early favourite while a later one is being
            // fetched. Report only a contiguous, fully cached resource — not
            // merely a request that once completed — so "offline" stays true.
            fetched.count { key ->
                // A streaming response may omit Content-Length, but Media3
                // records the discovered length while writing spans. Prefer it
                // over the initial DataSource answer for the final check.
                val length = ContentMetadata.getContentLength(cache(context).getContentMetadata(key))
                length != C.LENGTH_UNSET.toLong() && cache(context).isCached(key, 0, length)
            }
        }

    suspend fun cacheFavorites(context: Context): Int = cacheFavorites(context) { _, _ -> }

    suspend fun cacheAlbums(context: Context): Int = cacheAlbums(context) { _, _ -> }
}
