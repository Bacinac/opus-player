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

/** The Shield's screensaver: this day through the years it was photographed,
 * shown by the player's own page for photographs one after another — the page
 * the television also shows when the house asks for somebody of the family.
 * It lives with the player rather than in here, so what it shows changes with
 * a deploy and not with an install.
 *
 * The page shares the WebView cookie jar with Player, so a paired box needs no
 * second credential. */
class OpusDreamService : DreamService() {
    private var web: WebView? = null
    private val again = Handler(Looper.getMainLooper())

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
                    again.postDelayed({ web?.loadUrl(Opus.url(SHOW)) }, RETRY_MS)
                }

                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                    (view.parent as? ViewGroup)?.removeView(view)
                    view.destroy()
                    finish()
                    return true
                }
            }
            loadUrl(Opus.url(SHOW))
        }
        setContentView(web, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
    }

    override fun onDetachedFromWindow() {
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
        const val RETRY_MS = 30_000L
    }
}
