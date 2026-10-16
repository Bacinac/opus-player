package biz.boskovic.opus.music

import androidx.annotation.OptIn
import androidx.car.app.CarContext
import androidx.car.app.media.model.MediaPlaybackTemplate
import androidx.car.app.model.Action
import androidx.car.app.model.Header
import androidx.car.app.model.Template
import androidx.media3.common.util.UnstableApi

/** The now-playing surface. The transport controls and metadata are drawn by
 *  the host from the registered MediaSession, so the template only carries the
 *  header; [CarLink] registers that session's token before this screen opens. */
@OptIn(UnstableApi::class)
class PlaybackScreen(carContext: CarContext, link: CarLink) : CarScreen(carContext, link) {

    override fun onGetTemplate(): Template {
        val header = Header.Builder()
            .setStartHeaderAction(Action.BACK)
            .setTitle(carContext.getString(R.string.car_now_playing))
            .build()
        return MediaPlaybackTemplate.Builder().setHeader(header).build()
    }
}
