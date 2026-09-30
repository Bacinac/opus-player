package biz.boskovic.opus.music

import android.app.Application
import biz.boskovic.opus.core.CrashReporter

class MusicApp : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashReporter.install(this)
        CrashReporter.flush(this, Car.client(this))
    }
}
