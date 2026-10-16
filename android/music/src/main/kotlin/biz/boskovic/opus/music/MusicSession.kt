package biz.boskovic.opus.music

import android.content.Intent
import androidx.car.app.Screen
import androidx.car.app.Session
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner

class MusicSession : Session() {
    private var link: CarLink? = null

    init {
        lifecycle.addObserver(object : DefaultLifecycleObserver {
            override fun onDestroy(owner: LifecycleOwner) {
                link?.release()
                link = null
            }
        })
    }

    private fun link(): CarLink = link ?: CarLink(carContext).also { link = it }

    override fun onCreateScreen(intent: Intent): Screen = RootScreen(carContext, link())
}
