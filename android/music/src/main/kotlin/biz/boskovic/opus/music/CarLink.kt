package biz.boskovic.opus.music

import android.content.ComponentName
import android.media.session.MediaSession as PlatformSession
import android.os.Build
import android.os.Bundle
import android.support.v4.media.session.MediaSessionCompat
import androidx.annotation.OptIn
import androidx.car.app.CarContext
import androidx.car.app.media.MediaPlaybackManager
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.session.MediaController
import androidx.media3.session.SessionCommand
import androidx.media3.session.SessionToken
import com.google.common.util.concurrent.ListenableFuture
import kotlinx.coroutines.guava.await

/** The car-app screens browse the shelf straight through [MusicTree], but
 *  playback lives in [MusicService]. This connects a controller to that service
 *  to start playback, and registers the session's platform token with the Car
 *  App Library host so the MediaPlaybackTemplate draws the transport controls. */
@OptIn(UnstableApi::class)
class CarLink(private val carContext: CarContext) {
    private var connection: ListenableFuture<MediaController>? = null
    private var registered = false

    /** The id of what the session is playing, once a controller is connected;
     *  read on the main thread the controller is confined to, so the screens
     *  can mark the current item without forcing a connection of their own. */
    val nowPlaying: String?
        get() = connection?.takeIf { it.isDone }
            ?.let { runCatching { it.get().currentMediaItem?.mediaId }.getOrNull() }

    private suspend fun controller(): MediaController {
        val future = connection ?: MediaController.Builder(
            carContext.applicationContext,
            SessionToken(carContext, ComponentName(carContext, MusicService::class.java)),
        ).buildAsync().also { connection = it }
        val controller = future.await()
        if (!registered) {
            register(controller)
            registered = true
        }
        return controller
    }

    // MediaPlaybackManager still speaks the platform MediaSessionCompat.Token,
    // which androidx.media now deprecates; the car-app host leaves us no other
    // way to hand it this session's token.
    @Suppress("DEPRECATION")
    private suspend fun register(controller: MediaController) {
        val result = controller.sendCustomCommand(SessionCommand(PLATFORM_TOKEN, Bundle.EMPTY), Bundle.EMPTY).await()
        val token = platformToken(result.extras) ?: return
        (carContext.getCarService(CarContext.MEDIA_PLAYBACK_SERVICE) as MediaPlaybackManager)
            .registerMediaPlaybackToken(MediaSessionCompat.Token.fromToken(token))
    }

    private fun platformToken(extras: Bundle): PlatformSession.Token? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            extras.getParcelable(KEY_TOKEN, PlatformSession.Token::class.java)
        } else {
            @Suppress("DEPRECATION")
            extras.getParcelable(KEY_TOKEN)
        }

    suspend fun play(mediaId: String) {
        val controller = controller()
        controller.setMediaItem(MediaItem.Builder().setMediaId(mediaId).build())
        controller.prepare()
        controller.play()
    }

    fun release() {
        connection?.let(MediaController::releaseFuture)
        connection = null
        registered = false
    }

    companion object {
        const val PLATFORM_TOKEN = "biz.boskovic.opus.music.PLATFORM_TOKEN"
        const val KEY_TOKEN = "token"
    }
}
