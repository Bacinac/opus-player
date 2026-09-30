package biz.boskovic.opus.player

import android.app.Application
import android.content.Context
import android.webkit.CookieManager
import biz.boskovic.opus.core.CrashReporter
import biz.boskovic.opus.core.Opus
import biz.boskovic.opus.core.OpusHttp
import okhttp3.OkHttpClient

class PlayerApp : Application() {
    /** Whatever the page signed in with: the box's own cookie on a television,
     *  the person's on a phone. */
    val http: OkHttpClient by lazy {
        OpusHttp.client(Opus.userAgent(this)) { cookie()?.let { "Cookie" to it } }
    }

    override fun onCreate() {
        super.onCreate()
        CrashReporter.install(this)
    }

    companion object {
        fun cookie(): String? = CookieManager.getInstance().getCookie(Opus.origin.toString())

        fun http(context: Context): OkHttpClient = (context.applicationContext as PlayerApp).http
    }
}
