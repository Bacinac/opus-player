package biz.boskovic.opus.player

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Handler
import android.os.Looper
import android.service.dreams.DreamService
import android.view.ViewGroup
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import biz.boskovic.opus.core.Opus
import biz.boskovic.opus.core.OpusHttp
import java.io.IOException
import kotlinx.coroutines.MainScope
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONObject

/** The Shield's screensaver: this day through the years it was photographed,
 * shown by the player's own page for photographs one after another — the page
 * the television also shows when the house asks for somebody of the family.
 * It lives with the player rather than in here, so what it shows changes with
 * a deploy and not with an install. A profile that chose the cameras gets the
 * same wall Home opens, drawn still.
 *
 * The page shares the WebView cookie jar with Player, so a paired box needs no
 * second credential. */
class OpusDreamService : DreamService() {
    private var web: WebView? = null
    private val again = Handler(Looper.getMainLooper())
    private val scope = MainScope()

    // Android lint reports the WebViewClient super-constructor even though the
    // anonymous client below handles onRenderProcessGone explicitly.
    @SuppressLint("SetJavaScriptEnabled", "MissingOnRenderProcessGone")
    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        isInteractive = false
        isFullscreen = true
        isScreenBright = true
        web = WebView(this).apply {
            setBackgroundColor(Color.BLACK)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                    !Opus.ours(request.url)

                // A player that is down would leave the WebView's own error page
                // on the living-room wall all night: black instead, and asked again.
                override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                    if (!request.isForMainFrame) return
                    view.loadUrl("about:blank")
                    again.postDelayed(::choose, RETRY_MS)
                }

                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                    (view.parent as? ViewGroup)?.removeView(view)
                    view.destroy()
                    finish()
                    return true
                }
            }
        }
        setContentView(web, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        choose()
    }

    // asked of the player each time rather than kept here, because the profile
    // picked on the box may have changed its mind since the last screensaver
    private fun choose() {
        scope.launch {
            val chosen = try {
                OpusHttp.get(PlayerApp.http(this@OpusDreamService), CHOSEN)
            } catch (_: IOException) {
                web?.loadUrl("about:blank")
                again.postDelayed(::choose, RETRY_MS)
                return@launch
            }
            val page = web ?: return@launch
            if (JSONObject(chosen).optBoolean("cameras")) {
                page.loadDataWithBaseURL(Opus.url("/"), CameraWall.page(this@OpusDreamService, still = true),
                    "text/html", "utf-8", null)
            } else {
                page.loadUrl(Opus.url(SHOW))
            }
        }
    }

    override fun onDetachedFromWindow() {
        scope.cancel()
        again.removeCallbacksAndMessages(null)
        web?.apply {
            stopLoading()
            loadUrl("about:blank")
            destroy()
        }
        web = null
        super.onDetachedFromWindow()
    }

    private companion object {
        const val SHOW = "/show.html"
        const val CHOSEN = "/api/photos/screensaver"
        const val RETRY_MS = 30_000L
    }
}
