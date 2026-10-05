package biz.boskovic.opus.player

import android.Manifest
import android.annotation.SuppressLint
import android.app.AlertDialog
import android.app.UiModeManager
import android.app.role.RoleManager
import android.content.ComponentName
import android.content.Intent
import android.content.pm.ApplicationInfo
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.graphics.Color
import android.net.ConnectivityManager
import android.net.Network
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.os.SystemClock
import android.provider.Settings
import android.util.Log
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup.LayoutParams.MATCH_PARENT
import android.view.WindowManager
import android.webkit.CookieManager
import android.webkit.RenderProcessGoneDetail
import android.webkit.WebChromeClient
import android.webkit.ValueCallback
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.StringRes
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.core.text.htmlEncode
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import biz.boskovic.opus.core.R as CoreR
import biz.boskovic.opus.core.CrashReporter
import biz.boskovic.opus.core.Opus
import biz.boskovic.opus.core.Updater
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.math.roundToInt
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class PlayerActivity : ComponentActivity() {

    companion object {
        private const val TAG = "OpusPlayer"
        private const val ENABLE_HOME = "biz.boskovic.opus.player.ENABLE_HOME"
        private const val DISABLE_HOME = "biz.boskovic.opus.player.DISABLE_HOME"

        /** Kept in step with detect() in frontend/src/lib/keep/surface.svelte.ts,
         *  the only thing that reads it. */
        const val SAYS_TV = "OPUSPlayer/tv"
    }

    internal val gesture = Gesture(SystemClock::uptimeMillis)

    /** Android says no to an activity with more than one exception: not found,
     *  not permitted, a file address leaving the app, and others. */
    private fun start(intent: Intent, @StringRes unavailable: Int) {
        try {
            startActivity(intent)
        } catch (refused: RuntimeException) {
            Log.e(TAG, "could not open ${intent.component ?: intent.data?.scheme}", refused)
            Toast.makeText(this, unavailable, Toast.LENGTH_LONG).show()
        }
    }

    override fun dispatchTouchEvent(event: MotionEvent): Boolean {
        if (event.actionMasked == MotionEvent.ACTION_UP) gesture.felt()
        return super.dispatchTouchEvent(event)
    }

    private lateinit var root: FrameLayout
    private lateinit var web: WebView

    private lateinit var engine: Engine
    private var quiet = false
    private var customView: View? = null
    private var customViewCallback: WebChromeClient.CustomViewCallback? = null

    private var bridged = false
    private val updater by lazy { Updater(this, PlayerApp.http(this), "/api/app/apk.json", "/api/app/opus.apk") }
    private val prefs by lazy { getSharedPreferences("opus_player", MODE_PRIVATE) }
    private val notifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) Log.i(TAG, "notifications declined; uploads run without showing progress")
    }

    internal val hearing = Hearing(this) { said ->
        web.post { web.evaluateJavascript("window.opusHeard && window.opusHeard($said)", null) }
    }
    private var hearIn = ""
    private val microphone = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) hearing.listen(hearIn) else hearing.refused()
    }

    /** On the page's own view rather than the window, which the film's full
     *  screen already switches on and off for itself. */
    internal fun awake(on: Boolean) {
        web.keepScreenOn = on
    }

    /** A film handed to a box that is showing something else — Google TV's own
     *  Home, another app, the screensaver — is the household asking for the
     *  screen. Android lets an app in the background take it only while it is
     *  Home or allowed to draw over other apps; false when this box is neither. */
    internal fun forward(): Boolean {
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED)) return true
        setTurnScreenOn(true)
        startActivity(
            Intent(this, PlayerActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_REORDER_TO_FRONT),
        )
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.Q || Settings.canDrawOverlays(this) ||
            getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_HOME)
    }

    internal fun listen(language: String) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED) {
            hearing.listen(language)
        } else {
            hearIn = language
            microphone.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    private val chrome = object : WebChromeClient() {
        override fun onShowFileChooser(
            view: WebView, callback: ValueCallback<Array<Uri>>, params: FileChooserParams,
        ): Boolean {
            if (view !== web || !Opus.ours(view.url.orEmpty()) ||
                params.mode !in intArrayOf(FileChooserParams.MODE_OPEN, FileChooserParams.MODE_OPEN_MULTIPLE)) {
                callback.onReceiveValue(null)
                return true
            }
            if (!fileChoice.begin(callback::onReceiveValue)) return true
            try {
                val accepted = params.acceptTypes.flatMap { it.split(',') }.map { it.trim() }
                    .filter { it.contains('/') }.distinct()
                val pick = params.createIntent().apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    putExtra(Intent.EXTRA_ALLOW_MULTIPLE, params.mode == FileChooserParams.MODE_OPEN_MULTIPLE)
                    if (accepted.isNotEmpty()) {
                        type = accepted.singleOrNull() ?: "*/*"
                        putExtra(Intent.EXTRA_MIME_TYPES, accepted.toTypedArray())
                    }
                }
                files.launch(pick)
            } catch (failure: RuntimeException) {
                Log.e(TAG, "could not open the file provider", failure)
                fileChoice.finish(null)
                Toast.makeText(this@PlayerActivity, R.string.file_choice_unavailable, Toast.LENGTH_LONG).show()
            }
            return true
        }

        // The player enters fullscreen through the Fullscreen API on its stage
        // element, which a WebView answers by handing over a view to host.
        override fun onShowCustomView(view: View, callback: CustomViewCallback) {
            if (customView != null) {
                callback.onCustomViewHidden()
                return
            }
            customView = view
            customViewCallback = callback
            web.visibility = View.GONE
            root.addView(view, FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT))
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }

        override fun onHideCustomView() {
            val view = customView ?: return
            root.removeView(view)
            customView = null
            web.visibility = View.VISIBLE
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            customViewCallback?.onCustomViewHidden()
            customViewCallback = null
        }
    }

    private val fileChoice = FileChoice<Array<Uri>>()
    private val files = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        val chosen = WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
        val safe = chosen?.takeIf { uris ->
            uris.isNotEmpty() && uris.all { uri ->
                uri.scheme == "content" && uri.authority?.startsWith("$packageName.") != true &&
                    checkUriPermission(uri, Process.myPid(), Process.myUid(), Intent.FLAG_GRANT_READ_URI_PERMISSION) ==
                    PackageManager.PERMISSION_GRANTED
            }
        }
        if (chosen != null && safe == null) {
            Log.w(TAG, "file provider returned an unreadable or private URI")
            Toast.makeText(this, R.string.file_choice_unavailable, Toast.LENGTH_LONG).show()
        }
        fileChoice.finish(safe)
    }

    /** A box starts before its network is up, so a failure is tried again after
     *  a wait that doubles up to half a minute. */
    private var waitFor = 2_000L

    /** A failed navigation reports FINISHED as well, with the URL that failed;
     *  this is what tells the two apart. */
    private var failed = false
    private var retryUrl = Opus.url("/")
    private val retry = Runnable {
        if (bridged) {
            web.loadUrl(retryUrl)
        } else {
            Log.e(TAG, "this WebView cannot run document-start scripts, so the page is not given a bridge")
            web.loadDataWithBaseURL(null, page(getString(R.string.webview_outdated)), "text/html", "utf-8", null)
        }
    }

    private fun fail(view: WebView, message: String, url: String) {
        failed = true
        retryUrl = url
        view.loadDataWithBaseURL(
            null, page(message, url, getString(R.string.failure_retrying)), "text/html", "utf-8", null,
        )
        view.removeCallbacks(retry)
        view.postDelayed(retry, waitFor)
        waitFor = (waitFor * 2).coerceAtMost(30_000L)
    }

    private val network by lazy { getSystemService(ConnectivityManager::class.java) }

    private val onNetwork = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            runOnUiThread { again() }
        }
    }

    private fun again() {
        if (!failed) return
        web.removeCallbacks(retry)
        web.post(retry)
    }

    private val client = Client()

    // The detector reports every Kotlin super-constructor call, whether or not
    // the subclass overrides onRenderProcessGone; this one does.
    @SuppressLint("MissingOnRenderProcessGone")
    private inner class Client : WebViewClient() {
        override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
            fileChoice.cancel()
            if (Opus.ours(url)) failed = false
            engine.orphaned()
        }

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            if (Opus.ours(request.url)) return false
            if (gesture.leaves(request.isForMainFrame)) {
                start(Intent(Intent.ACTION_VIEW, request.url), R.string.link_unavailable)
            } else {
                Log.w(TAG, "refused to leave for ${request.url.scheme}://${request.url.host}: not the page itself in answer to a key or a tap")
            }
            return true
        }

        override fun onReceivedError(
            view: WebView,
            request: WebResourceRequest,
            error: WebResourceError,
        ) {
            if (!request.isForMainFrame) return
            fail(view, error.description.toString(), request.url.toString())
        }

        // A tunnel that is not up yet answers 502 instead of failing to connect.
        // Only 5xx: a 401 from pairing is a screen, and retrying would hide it.
        override fun onReceivedHttpError(
            view: WebView,
            request: WebResourceRequest,
            response: WebResourceResponse,
        ) {
            if (!request.isForMainFrame || response.statusCode < 500) return
            fail(view, "HTTP ${response.statusCode}", request.url.toString())
        }

        override fun onPageFinished(view: WebView, url: String) {
            // Also fires for the navigation that failed, just after fail()
            // posted its retry, which this must not cancel.
            if (failed || !Opus.ours(url)) return
            waitFor = 2_000L
            view.removeCallbacks(retry)
        }

        /** Unanswered, a dead renderer takes the app down with it. The page is
         *  planted again; a record plays on, a film stops with the page that
         *  was showing it. */
        override fun onRenderProcessGone(view: WebView, detail: RenderProcessGoneDetail): Boolean {
            fileChoice.cancel()
            Log.e(TAG, "page renderer gone (crashed: ${detail.didCrash()}); loading the page again")
            engine.orphaned()
            customView?.let { root.removeView(it) }
            customView = null
            customViewCallback = null
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            root.removeView(view)
            view.destroy()
            plant()
            retryUrl = Opus.url("/")
            web.post(retry)
            return true
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun plant() {
        // Felt before dispatch: the WebView hands a key listener only what the
        // page left unhandled, after the page, and the page handles OK itself.
        web = object : WebView(this) {
            override fun dispatchKeyEvent(event: KeyEvent): Boolean {
                if (event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0 &&
                    Gesture.activates(event.keyCode)) gesture.felt()
                // the remote's microphone key, while the page has letters up for
                // the words to go into; anywhere else it stays the box's search
                if (event.keyCode == KeyEvent.KEYCODE_SEARCH && hearing.wanted) {
                    if (event.action == KeyEvent.ACTION_UP) {
                        evaluateJavascript("window.opusListen && window.opusListen()", null)
                    }
                    return true
                }
                return super.dispatchKeyEvent(event)
            }
        }.apply {
            layoutParams = FrameLayout.LayoutParams(MATCH_PARENT, MATCH_PARENT)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            if (isTelevision()) settings.userAgentString = settings.userAgentString + " " + SAYS_TV
            // A remote has nothing to tap with, so no user gesture ever precedes playback.
            settings.mediaPlaybackRequiresUserGesture = false
            // Off a remote a WebView answers requestFocus() by dropping the page's
            // own focus and tabbing to the first node, ring and all; after the
            // panel switch the page gets back exactly what it had.
            settings.setNeedInitialFocus(false)
            webChromeClient = chrome
            webViewClient = client
            // The picture is drawn underneath the page.
            setBackgroundColor(Color.TRANSPARENT)
        }
        bridged = OpusTv(this, engine).attach(web)
        root.addView(web)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        configureHome(intent)

        // DevTools may be useful over adb while developing a television UI,
        // but a release WebView can hold a household session and must not
        // expose its page to a locally attached debugger.
        WebView.setWebContentsDebuggingEnabled(
            isTelevision() && applicationInfo.flags.and(ApplicationInfo.FLAG_DEBUGGABLE) != 0
        )

        setContentView(R.layout.stage)
        root = findViewById(android.R.id.content)
        engine = Engine(this, findViewById(R.id.screen))
        plant()
        root.setOnKeyListener { _, _, _ -> quiet }
        engine.onQuiet = { on ->
            quiet = on
            if (on) {
                root.isFocusable = true
                root.requestFocus()
                web.visibility = View.INVISIBLE
            } else {
                web.visibility = View.VISIBLE
                root.isFocusable = false
                web.requestFocus()
            }
        }
        engine.onKey = { command ->
            web.post { web.evaluateJavascript("window.opusTvKey && window.opusTvKey('$command')", null) }
        }
        CrashReporter.flush(this, PlayerApp.http(this))

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (customView != null) {
                    chrome.onHideCustomView()
                    return
                }
                // The page is asked first: while a film plays, back means leave the film.
                web.evaluateJavascript("!!(window.opusBack && window.opusBack())") { answer ->
                    if (answer == "true") return@evaluateJavascript
                    if (web.canGoBack()) web.goBack() else finish()
                }
            }
        })

        // restoreState answers null when nothing was restorable, and about:blank
        // loads without the error that would schedule a retry.
        if (savedInstanceState == null ||
            web.restoreState(savedInstanceState) == null ||
            web.url?.let(Opus::ours) != true
        ) {
            web.post(retry)
        }

        // A recreated activity is handed its original intent again, and a share
        // is offered once.
        if (savedInstanceState == null) take(intent)

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                GivenService.told.collect { told ->
                    if (told == null) return@collect
                    GivenService.heard()
                    web.loadUrl(Opus.url("/photos?given=${told.sent}&known=${told.known}&failed=${told.failed}"))
                }
            }
        }

        network.registerDefaultNetworkCallback(onNetwork)
    }

    private fun isTelevision(): Boolean =
        getSystemService(UiModeManager::class.java).currentModeType == Configuration.UI_MODE_TYPE_TELEVISION

    /** NVIDIA does not let the adb shell change an application's disabled
     *  component. The Shield scripts instead ask the running television app
     *  to change its own Home entry. A normal launch, including one on a
     *  phone, never changes it. */
    private fun configureHome(intent: Intent) {
        if (!isTelevision()) return
        val state = when {
            intent.getBooleanExtra(ENABLE_HOME, false) -> PackageManager.COMPONENT_ENABLED_STATE_ENABLED
            intent.getBooleanExtra(DISABLE_HOME, false) -> PackageManager.COMPONENT_ENABLED_STATE_DISABLED
            else -> return
        }
        packageManager.setComponentEnabledSetting(
            ComponentName(this, HomeActivity::class.java),
            state,
            PackageManager.DONT_KILL_APP,
        )
    }

    /** singleTask: a second share reaches the activity that is already here. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        configureHome(intent)
        take(intent)
    }

    private fun take(intent: Intent) {
        val offered = GivenService.of(intent) ?: return
        setIntent(Intent(Intent.ACTION_MAIN))
        lifecycleScope.launch {
            val sorted = withContext(Dispatchers.IO) { Offered.sort(this@PlayerActivity, offered) }
            confirm(sorted)
        }
    }

    private fun confirm(sorted: Offered.Sorted) {
        if (isFinishing || isDestroyed) return
        val refusal = buildList {
            if (sorted.refused > 0) add(getString(R.string.given_refused, sorted.refused))
            add(getString(R.string.given_rule))
        }
        if (sorted.accepted.isEmpty()) {
            AlertDialog.Builder(this)
                .setTitle(R.string.given_nothing)
                .setMessage(refusal.joinToString("\n"))
                .setPositiveButton(android.R.string.ok, null)
                .show()
            return
        }
        val count = getString(R.string.given_count, sorted.accepted.size)
        AlertDialog.Builder(this)
            .setTitle(R.string.given_confirm)
            .setMessage(if (sorted.refused > 0) (listOf(count) + refusal).joinToString("\n") else count)
            .setView(strip(sorted.thumbnails))
            .setPositiveButton(R.string.given_send) { _, _ -> send(sorted.accepted) }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun strip(pictures: List<Bitmap>): View? {
        if (pictures.isEmpty()) return null
        val dp = resources.displayMetrics.density
        val side = (72 * dp).roundToInt()
        val gap = (8 * dp).roundToInt()
        val row = LinearLayout(this).apply { setPadding(gap * 3, gap * 2, gap * 3, 0) }
        for (picture in pictures) {
            row.addView(
                ImageView(this).apply {
                    setImageBitmap(picture)
                    scaleType = ImageView.ScaleType.CENTER_CROP
                    importantForAccessibility = View.IMPORTANT_FOR_ACCESSIBILITY_NO
                },
                LinearLayout.LayoutParams(side, side).apply { marginEnd = gap },
            )
        }
        return HorizontalScrollView(this).apply { addView(row) }
    }

    private fun send(pictures: List<Uri>) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        GivenService.start(this, pictures)
    }

    /** A WebView holds its cookies in memory until told to write them, and the
     *  session is one of them. */
    override fun onPause() {
        super.onPause()
        CookieManager.getInstance().flush()
        engine.leave()
    }

    /** Leaving and coming back is what a person does with a stuck screen, and a
     *  singleTask instance resumes on the same failure page. */
    override fun onResume() {
        super.onResume()
        setTurnScreenOn(false)
        again()
        lifecycleScope.launch { offerUpdate() }
    }

    override fun onStop() {
        super.onStop()
        engine.hidden()
    }

    private suspend fun offerUpdate() {
        val now = System.currentTimeMillis()
        if (engine.busy() || now - prefs.getLong("update_checked_at", 0L) < TimeUnit.HOURS.toMillis(6)) return
        val offer = try {
            updater.offer()
        } catch (failure: IOException) {
            Log.w(TAG, "update check failed", failure)
            return
        }
        prefs.edit { putLong("update_checked_at", now) }
        if (offer == null || isFinishing) return
        AlertDialog.Builder(this)
            .setTitle(CoreR.string.update_title)
            .setMessage(CoreR.string.update_body)
            .setPositiveButton(CoreR.string.update_install) { _, _ ->
                lifecycleScope.launch {
                    try {
                        updater.install(this@PlayerActivity, updater.download(offer))
                    } catch (failure: IOException) {
                        Log.e(TAG, "update ${offer.versionCode} failed", failure)
                        Toast.makeText(
                            this@PlayerActivity,
                            getString(CoreR.string.update_failed, failure.message),
                            Toast.LENGTH_LONG,
                        ).show()
                    }
                }
            }
            .setNegativeButton(CoreR.string.update_later, null)
            .show()
    }

    override fun onDestroy() {
        fileChoice.cancel()
        network.unregisterNetworkCallback(onNetwork)
        web.removeCallbacks(retry)
        hearing.release()
        root.removeView(web)
        web.destroy()
        super.onDestroy()
        engine.release()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        web.saveState(outState)
    }

    private fun page(message: String, vararg notes: String): String {
        fun hex(color: Int) = "#%06x".format(ContextCompat.getColor(this, color) and 0xffffff)
        val below = notes.joinToString("") {
            """<div style="margin-top:12px;opacity:.6;font-size:18px">${it.htmlEncode()}</div>"""
        }
        return """
            <html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
            <body style="margin:0;display:flex;align-items:center;justify-content:center;
                         height:100vh;background:${hex(CoreR.color.opus_bg)};color:${hex(CoreR.color.opus_text)};
                         font:400 24px/1.5 system-ui,sans-serif;text-align:center">
              <div><div style="color:${hex(CoreR.color.opus_soft)};font-weight:700">OPUS</div>
              <div style="margin-top:16px">${message.htmlEncode()}</div>$below</div>
            </body></html>
        """.trimIndent()
    }
}
