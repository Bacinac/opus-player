package biz.boskovic.opus.music

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.annotation.OptIn
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DataSourceBitmapLoader
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.CacheBitmapLoader
import androidx.media3.session.LibraryResult
import androidx.media3.session.MediaConstants
import androidx.media3.session.MediaLibraryService
import androidx.media3.session.MediaSession
import androidx.media3.session.SessionError
import biz.boskovic.opus.core.R as CoreR
import biz.boskovic.opus.core.Refused
import biz.boskovic.opus.core.Updater
import com.google.common.collect.ImmutableList
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import com.google.common.util.concurrent.ListeningExecutorService
import com.google.common.util.concurrent.MoreExecutors
import java.io.IOException
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.guava.future
import kotlinx.coroutines.launch
import org.json.JSONException

@OptIn(UnstableApi::class)
class MusicService : MediaLibraryService() {
    private lateinit var session: MediaLibrarySession
    private lateinit var pictures: ListeningExecutorService
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val checkpoints = Handler(Looper.getMainLooper())
    private val checkpoint = object : Runnable {
        override fun run() {
            // Position changes do not emit a Player event. A process killed
            // while a long record is playing would otherwise restore the
            // position from the last pause or track change.
            if (session.player.mediaItemCount > 0) Kept.save(this@MusicService, session.player)
            checkpoints.postDelayed(this, CHECKPOINT_MS)
        }
    }

    override fun onCreate() {
        super.onCreate()
        val sources = ListeningCache.source(this, OkHttpDataSource.Factory(Car.client(this)))
        val player = ExoPlayer.Builder(this)
            .setMediaSourceFactory(DefaultMediaSourceFactory(sources))
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(C.USAGE_MEDIA).setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(),
                true,
            )
            .setHandleAudioBecomingNoisy(true)
            .setWakeMode(C.WAKE_MODE_NETWORK)
            .build()
        player.addListener(object : Player.Listener {
            override fun onEvents(player: Player, events: Player.Events) {
                if (events.containsAny(
                        Player.EVENT_MEDIA_ITEM_TRANSITION,
                        Player.EVENT_IS_PLAYING_CHANGED,
                        Player.EVENT_TIMELINE_CHANGED,
                    )
                ) {
                    Kept.save(this@MusicService, player)
                }
                if (events.contains(Player.EVENT_MEDIA_ITEM_TRANSITION)) {
                    player.currentMediaItem?.let { Kept.remember(this@MusicService, it) }
                }
            }
        })
        pictures = MoreExecutors.listeningDecorator(Executors.newSingleThreadExecutor())
        session = MediaLibrarySession.Builder(this, player, Tree())
            .setBitmapLoader(
                CacheBitmapLoader(
                    DataSourceBitmapLoader.Builder(this)
                        .setDataSourceFactory(sources)
                        .setExecutorService(pictures)
                        .build()
                )
            )
            .build()
        checkpoints.postDelayed(checkpoint, CHECKPOINT_MS)
        scope.launch { offerUpdate() }
        scope.launch {
            Car.forgotten.drop(1).collect {
                player.stop()
                player.clearMediaItems()
            }
        }
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaLibrarySession = session

    override fun onDestroy() {
        scope.cancel()
        checkpoints.removeCallbacks(checkpoint)
        Kept.save(this, session.player)
        session.player.release()
        session.release()
        pictures.shutdown()
        super.onDestroy()
    }

    /** Checked from here because the car is where the app is used; offered as a
     *  notification, never as anything that asks for attention while driving. */
    private suspend fun offerUpdate() {
        val now = System.currentTimeMillis()
        if (now - Car.updateCheckedAt(this) < TimeUnit.HOURS.toMillis(12)) return
        val offer = try {
            Updater(this, Car.client(this), "/api/app/music.json", "/api/app/opus-music.apk").offer()
        } catch (failure: IOException) {
            Log.w(TAG, "update check failed", failure)
            return
        }
        Car.updateChecked(this, now)
        if (offer == null) return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            Log.w(TAG, "update ${offer.versionCode} is waiting; notifications are not allowed")
            return
        }
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(UPDATES, getString(CoreR.string.update_channel), NotificationManager.IMPORTANCE_LOW)
        )
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, SetupActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        NotificationManagerCompat.from(this).notify(
            UPDATE_NOTICE,
            NotificationCompat.Builder(this, UPDATES)
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle(getString(CoreR.string.update_title))
                .setContentText(getString(R.string.update_ready))
                .setContentIntent(open)
                .setAutoCancel(true)
                .build(),
        )
    }

    private fun failure(error: Exception): SessionError = when (error) {
        is NotPaired -> signIn(getString(R.string.car_not_paired))
        is VaultUnavailable -> signIn(getString(R.string.car_vault_unavailable))
        is Refused -> signIn(getString(R.string.car_refused))
        else -> SessionError(SessionError.ERROR_IO, getString(R.string.car_unreachable))
    }

    private fun signIn(message: String): SessionError {
        val pair = PendingIntent.getActivity(
            this, 0, Intent(this, SetupActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
        )
        return SessionError(
            SessionError.ERROR_SESSION_AUTHENTICATION_EXPIRED,
            message,
            Bundle().apply {
                putString(MediaConstants.EXTRAS_KEY_ERROR_RESOLUTION_ACTION_LABEL_COMPAT, getString(R.string.car_pair))
                putParcelable(MediaConstants.EXTRAS_KEY_ERROR_RESOLUTION_ACTION_INTENT_COMPAT, pair)
            },
        )
    }

    private inner class Tree : MediaLibrarySession.Callback {
        override fun onConnect(session: MediaSession, controller: MediaSession.ControllerInfo): MediaSession.ConnectionResult {
            if (Controllers.admits(controller.packageName, controller.isPackageNameVerified, controller.isTrusted)) {
                return MediaSession.ConnectionResult.accept(
                    MediaSession.ConnectionResult.DEFAULT_SESSION_AND_LIBRARY_COMMANDS,
                    MediaSession.ConnectionResult.DEFAULT_PLAYER_COMMANDS,
                )
            }
            Log.w(TAG, "refused a controller from ${controller.packageName}")
            return MediaSession.ConnectionResult.reject()
        }

        override fun onGetLibraryRoot(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            params: LibraryParams?,
        ): ListenableFuture<LibraryResult<MediaItem>> =
            Futures.immediateFuture(LibraryResult.ofItem(MusicTree.root(this@MusicService), params))

        override fun onGetChildren(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            parentId: String,
            page: Int,
            pageSize: Int,
            params: LibraryParams?,
        ): ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> = scope.future {
            answer(params) { MusicTree.children(this@MusicService, parentId).page(page, pageSize) }
        }

        override fun onGetItem(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            mediaId: String,
        ): ListenableFuture<LibraryResult<MediaItem>> = scope.future {
            try {
                LibraryResult.ofItem(MusicTree.playable(this@MusicService, mediaId), null)
            } catch (unknown: IllegalArgumentException) {
                LibraryResult.ofError(SessionError(SessionError.ERROR_BAD_VALUE, unknown.message ?: mediaId))
            } catch (error: IOException) {
                LibraryResult.ofError(failure(error))
            } catch (error: JSONException) {
                LibraryResult.ofError(failure(error))
            }
        }

        override fun onSearch(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            query: String,
            params: LibraryParams?,
        ): ListenableFuture<LibraryResult<Void>> = scope.future {
            try {
                val hits = MusicTree.search(this@MusicService, query)
                session.notifySearchResultChanged(browser, query, hits.size, params)
                LibraryResult.ofVoid(params)
            } catch (error: IOException) {
                LibraryResult.ofError(failure(error))
            } catch (error: JSONException) {
                LibraryResult.ofError(failure(error))
            }
        }

        override fun onGetSearchResult(
            session: MediaLibrarySession,
            browser: MediaSession.ControllerInfo,
            query: String,
            page: Int,
            pageSize: Int,
            params: LibraryParams?,
        ): ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> = scope.future {
            answer(params) { MusicTree.searched(this@MusicService, query).page(page, pageSize) }
        }

        override fun onAddMediaItems(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            mediaItems: MutableList<MediaItem>,
        ): ListenableFuture<MutableList<MediaItem>> = scope.future {
            val query = voiceQuery(mediaItems)
            queued(mediaSession) {
                if (query != null) MusicTree.search(this@MusicService, query)
                else if (mediaItems.singleOrNull()?.mediaId == MusicTree.CONTINUE) {
                    Kept.restore(this@MusicService)?.mediaItems.orEmpty()
                }
                else mediaItems.map { MusicTree.playable(this@MusicService, it.mediaId) }
            }.toMutableList()
        }

        override fun onSetMediaItems(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            mediaItems: MutableList<MediaItem>,
            startIndex: Int,
            startPositionMs: Long,
        ): ListenableFuture<MediaSession.MediaItemsWithStartPosition> = scope.future {
            val query = voiceQuery(mediaItems)
            when {
                query != null -> MediaSession.MediaItemsWithStartPosition(
                    queued(mediaSession) { MusicTree.search(this@MusicService, query) }, 0, 0L,
                )
                mediaItems.singleOrNull()?.mediaId == MusicTree.CONTINUE -> try {
                    Kept.restore(this@MusicService)
                        ?: MediaSession.MediaItemsWithStartPosition(emptyList(), 0, 0L)
                } catch (corrupt: JSONException) {
                    Kept.drop(this@MusicService)
                    MediaSession.MediaItemsWithStartPosition(emptyList(), 0, 0L)
                }
                mediaItems.size == 1 -> {
                    var index = 0
                    val queue = queued(mediaSession) {
                        MusicTree.queueFrom(this@MusicService, mediaItems[0].mediaId).let { (queue, at) ->
                            index = at
                            queue
                        }
                    }
                    MediaSession.MediaItemsWithStartPosition(queue, index, startPositionMs)
                }
                else -> MediaSession.MediaItemsWithStartPosition(
                    queued(mediaSession) { mediaItems.map { MusicTree.playable(this@MusicService, it.mediaId) } },
                    startIndex,
                    startPositionMs,
                )
            }
        }

        override fun onPlaybackResumption(
            mediaSession: MediaSession,
            controller: MediaSession.ControllerInfo,
            isForPlayback: Boolean,
        ): ListenableFuture<MediaSession.MediaItemsWithStartPosition> {
            if (!Car.paired(this@MusicService) || Car.refused(this@MusicService)) {
                Kept.drop(this@MusicService)
                return Futures.immediateFailedFuture(NotPaired())
            }
            val kept = try {
                Kept.restore(this@MusicService)
            } catch (corrupt: JSONException) {
                Log.e(TAG, "the kept queue is unreadable and is dropped", corrupt)
                Kept.drop(this@MusicService)
                return Futures.immediateFailedFuture(corrupt)
            } ?: return Futures.immediateFailedFuture(UnsupportedOperationException("nothing has been played yet"))
            return Futures.immediateFuture(kept)
        }

        private suspend fun answer(
            params: LibraryParams?,
            load: suspend () -> List<MediaItem>,
        ): LibraryResult<ImmutableList<MediaItem>> = try {
            LibraryResult.ofItemList(load(), params)
        } catch (unknown: IllegalArgumentException) {
            LibraryResult.ofError(SessionError(SessionError.ERROR_BAD_VALUE, unknown.message.orEmpty()))
        } catch (error: IOException) {
            LibraryResult.ofError(failure(error))
        } catch (error: JSONException) {
            LibraryResult.ofError(failure(error))
        }

        private suspend fun queued(session: MediaSession, load: suspend () -> List<MediaItem>): List<MediaItem> = try {
            load()
        } catch (unknown: IllegalArgumentException) {
            session.sendError(SessionError(SessionError.ERROR_BAD_VALUE, unknown.message.orEmpty()))
            emptyList()
        } catch (error: IOException) {
            session.sendError(failure(error))
            emptyList()
        } catch (error: JSONException) {
            session.sendError(failure(error))
            emptyList()
        }

        private fun voiceQuery(items: List<MediaItem>): String? {
            val only = items.singleOrNull() ?: return null
            if (only.mediaId.isNotEmpty()) return null
            return only.requestMetadata.searchQuery?.takeIf { it.isNotBlank() }
        }
    }

    private fun <T> List<T>.page(page: Int, size: Int): List<T> =
        if (size <= 0 || size == Int.MAX_VALUE) this else drop(page * size).take(size)

    companion object {
        private const val TAG = "OpusMusic"
        private const val CHECKPOINT_MS = 15_000L
        private const val UPDATES = "updates"
        private const val UPDATE_NOTICE = 1
    }
}
