package biz.boskovic.opus.music

import android.app.SearchManager
import android.content.ComponentName
import android.os.Bundle
import android.util.Log
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.session.MediaController
import androidx.media3.session.SessionToken
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.guava.await
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/** "Play X on OPUS Music" arriving as an intent: handed to the session the
 *  same way Android Auto's voice reaches it, then out of the way. */
class SearchActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE)
        val query = intent.getStringExtra(SearchManager.QUERY).orEmpty().trim()
        lifecycleScope.launch {
            val token = SessionToken(this@SearchActivity, ComponentName(this@SearchActivity, MusicService::class.java))
            val controller = try {
                MediaController.Builder(this@SearchActivity, token).buildAsync().await()
            } catch (refused: SecurityException) {
                Log.e(TAG, "voice request \"$query\" could not reach the music session", refused)
                Toast.makeText(applicationContext, R.string.search_failed, Toast.LENGTH_LONG).show()
                finish()
                return@launch
            }
            try {
                val started = CompletableDeferred<Unit>()
                controller.addListener(object : Player.Listener {
                    override fun onIsPlayingChanged(isPlaying: Boolean) {
                        if (isPlaying) started.complete(Unit)
                    }

                    override fun onPlaybackStateChanged(playbackState: Int) {
                        if (playbackState == Player.STATE_ENDED) started.complete(Unit)
                    }

                    override fun onPlayerError(error: PlaybackException) {
                        Log.w(TAG, "voice request \"$query\" did not play", error)
                        started.complete(Unit)
                    }
                })
                if (query.isNotEmpty()) {
                    controller.setMediaItem(
                        MediaItem.Builder()
                            .setRequestMetadata(MediaItem.RequestMetadata.Builder().setSearchQuery(query).build())
                            .build()
                    )
                    controller.prepare()
                }
                controller.play()
                if (withTimeoutOrNull(10_000) { started.await() } == null) {
                    Log.w(TAG, "voice request \"$query\" had not started after 10 s")
                }
            } finally {
                controller.release()
                finish()
            }
        }
    }

    private companion object {
        const val TAG = "OpusMusicSearch"
    }
}
