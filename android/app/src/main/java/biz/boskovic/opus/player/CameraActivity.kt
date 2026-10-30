package biz.boskovic.opus.player

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.KeyEvent
import android.view.ViewGroup
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import biz.boskovic.opus.core.Opus

/** A television-first wall of every camera DIDA exposes to this OPUS box.
 *
 * The browser receives only OPUS proxy paths. Camera addresses and DIDA's
 * machine credential stay on the servers, while the shared Player cookie keeps
 * this surface within the paired box session. */
class CameraActivity : ComponentActivity() {
    private var web: WebView? = null
    private val keys = Handler(Looper.getMainLooper())
    private var centerDown = false
    private var centerLong = false
    private val centerLongPress = Runnable {
        if (!centerDown) return@Runnable
        triggerCenterLongPress()
    }

    @SuppressLint("SetJavaScriptEnabled", "MissingOnRenderProcessGone")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        web = object : WebView(this) {
            override fun dispatchKeyEvent(event: KeyEvent): Boolean =
                when {
                    handleCenter(event) -> true
                    handleArrow(event) -> true
                    else -> super.dispatchKeyEvent(event)
                }
        }.apply {
            setBackgroundColor(Color.BLACK)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = false
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                    !Opus.ours(request.url)

                override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
                    (view.parent as? ViewGroup)?.removeView(view)
                    view.destroy()
                    finish()
                    return true
                }
            }
            loadDataWithBaseURL(Opus.url("/"), CameraWall.page(this@CameraActivity), "text/html", "utf-8", null)
        }
        setContentView(web, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT,
        ))
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val page = web
                if (page == null) {
                    finish()
                    return
                }
                page.evaluateJavascript("window.leaveCameraView && window.leaveCameraView()") { handled ->
                    if (handled != "true") {
                        isEnabled = false
                        onBackPressedDispatcher.onBackPressed()
                    }
                }
            }
        })
    }

    override fun onDestroy() {
        keys.removeCallbacks(centerLongPress)
        web?.apply {
            stopLoading()
            loadUrl("about:blank")
            destroy()
        }
        web = null
        super.onDestroy()
    }

    private fun handleCenter(event: KeyEvent): Boolean {
        if (event.keyCode != KeyEvent.KEYCODE_DPAD_CENTER &&
            event.keyCode != KeyEvent.KEYCODE_ENTER) {
            return false
        }
        if (event.action == KeyEvent.ACTION_DOWN && !centerDown) {
            centerDown = true
            centerLong = false
            keys.postDelayed(centerLongPress, LONG_PRESS_MS)
            if (event.isLongPress || event.repeatCount > 0) triggerCenterLongPress()
        } else if (event.action == KeyEvent.ACTION_DOWN && !centerLong && event.repeatCount > 0) {
            triggerCenterLongPress()
        } else if (event.action == KeyEvent.ACTION_UP) {
            keys.removeCallbacks(centerLongPress)
            if (centerDown && !centerLong) {
                web?.evaluateJavascript("window.pressFocused && window.pressFocused()", null)
            }
            centerDown = false
            centerLong = false
        }
        return true
    }

    private fun triggerCenterLongPress() {
        if (!centerDown || centerLong) return
        keys.removeCallbacks(centerLongPress)
        centerLong = true
        web?.evaluateJavascript("window.longPressFocused && window.longPressFocused()", null)
    }

    /** Some Android TV WebViews consume DPAD arrows for their own scrolling.
     * Forward them explicitly so the wall remains browsable with every Shield
     * remote and gamepad, while the page still owns the actual focus logic. */
    private fun handleArrow(event: KeyEvent): Boolean {
        val direction = when (event.keyCode) {
            KeyEvent.KEYCODE_DPAD_LEFT -> "left"
            KeyEvent.KEYCODE_DPAD_RIGHT -> "right"
            KeyEvent.KEYCODE_DPAD_UP -> "up"
            KeyEvent.KEYCODE_DPAD_DOWN -> "down"
            else -> return false
        }
        if (event.action == KeyEvent.ACTION_DOWN) {
            web?.evaluateJavascript("window.moveFocus && window.moveFocus('$direction')", null)
        }
        return true
    }

    companion object {
        private const val LONG_PRESS_MS = 600L
    }
}
