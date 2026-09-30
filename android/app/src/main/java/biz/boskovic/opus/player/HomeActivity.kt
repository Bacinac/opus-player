package biz.boskovic.opus.player

import android.app.AlertDialog
import android.content.ComponentName
import android.content.Intent
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.StateListDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.content.ContextCompat
import androidx.core.net.toUri
import androidx.core.view.children
import androidx.lifecycle.lifecycleScope
import biz.boskovic.opus.core.OpusHttp
import java.text.NumberFormat
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.roundToInt
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject

/** The box's native, offline Home surface.
 *
 * Apps, clock and date remain useful without a server. Household facts are a
 * small optional enhancement fetched through Player's existing box session. */
class HomeActivity : ComponentActivity() {

    private val apps by lazy { HomeApps(packageManager) }
    private val clock = Handler(Looper.getMainLooper())
    private lateinit var time: TextView
    private lateinit var date: TextView
    private lateinit var facts: LinearLayout
    private lateinit var grid: LinearLayout
    private var glanceJob: Job? = null
    private var appsNeedRefresh = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = Unit
        })
        setContentView(frame())
        drawApps()
    }

    override fun onResume() {
        super.onResume()
        if (appsNeedRefresh) {
            appsNeedRefresh = false
            drawApps()
        }
        updateClock()
        clock.post(clockTick)
        glanceJob?.cancel()
        glanceJob = lifecycleScope.launch {
            while (isActive) {
                refreshFacts()
                delay(GLANCE_REFRESH_MS)
            }
        }
    }

    override fun onPause() {
        glanceJob?.cancel()
        glanceJob = null
        clock.removeCallbacks(clockTick)
        super.onPause()
    }

    override fun onKeyLongPress(keyCode: Int, event: KeyEvent): Boolean {
        if (keyCode == KeyEvent.KEYCODE_MENU) {
            open(Intent(android.provider.Settings.ACTION_SETTINGS))
            return true
        }
        return super.onKeyLongPress(keyCode, event)
    }

    private val clockTick = object : Runnable {
        override fun run() {
            updateClock()
            clock.postDelayed(this, CLOCK_REFRESH_MS)
        }
    }

    private fun frame(): View {
        val root = FrameLayout(this).apply {
            clipChildren = false
            background = GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                intArrayOf(color(CoreColor.BG), Color.rgb(10, 25, 26), color(CoreColor.BG)),
            )
        }
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            clipChildren = false
            setPadding(dp(36), dp(22), dp(36), dp(24))
        }
        body.addView(topBar(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(76)))
        body.addView(View(this), LinearLayout.LayoutParams(1, 0, 1f))
        body.addView(appGrid(), LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT))
        root.addView(body, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
        return root
    }

    private fun topBar(): View = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(18), 0, dp(10), 0)
        background = rounded(Color.argb(105, 24, 31, 32), dp(14).toFloat())
        val whenNow = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_VERTICAL
            time = TextView(context).apply {
                setTextColor(color(CoreColor.TEXT))
                textSize = 32f
                setTypeface(typeface, Typeface.BOLD)
                includeFontPadding = false
            }
            date = TextView(context).apply {
                setTextColor(color(CoreColor.TEXT_DIM))
                textSize = 14f
                includeFontPadding = false
                setPadding(dp(1), dp(3), 0, 0)
            }
            addView(time)
            addView(date)
        }
        addView(whenNow, LinearLayout.LayoutParams(dp(184), ViewGroup.LayoutParams.MATCH_PARENT))
        addView(View(context).apply {
            setBackgroundColor(Color.argb(55, 138, 160, 166))
        }, LinearLayout.LayoutParams(dp(1), dp(38)))
        facts = LinearLayout(context).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        addView(facts, LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f))
    }

    private fun appGrid(): View = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        clipChildren = false
        clipToPadding = false
        grid = this
    }

    private fun drawApps(focusKey: String? = null) {
        grid.removeAllViews()
        val primary = orderedPackages().mapNotNull { wanted ->
            if (wanted == packageName) {
                HomeApps.App(ComponentName(this, PlayerActivity::class.java), getString(R.string.app_name))
            } else {
                apps.named(wanted)
            }
        }
        val camera = HomeApps.App(ComponentName(this, CameraActivity::class.java), getString(R.string.home_cameras))
        val available = (primary + camera).associateBy(::appKey)
        val shown = HomeOrder.items(this).mapNotNull(available::get)
        val rows = shown.chunked(TILES_PER_ROW)
        rows.forEach { rowApps ->
            val row = LinearLayout(this).apply {
                orientation = LinearLayout.HORIZONTAL
                gravity = Gravity.CENTER
                clipChildren = false
                clipToPadding = false
            }
            rowApps.forEach { app ->
                row.addView(tile(app), LinearLayout.LayoutParams(dp(TILE_WIDTH_DP), dp(TILE_HEIGHT_DP)).apply {
                    setMargins(dp(7), dp(7), dp(7), dp(7))
                })
            }
            grid.addView(row, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(TILE_HEIGHT_DP + 14)))
        }
        val tiles = grid.children.flatMap { child ->
            if (child is ViewGroup) child.children.toList() else listOf(child)
        }
        grid.post {
            tiles.firstOrNull { it.tag == focusKey }?.requestFocus()
                ?: tiles.firstOrNull()?.requestFocus()
        }
    }

    private fun tile(app: HomeApps.App): View {
        var held = false
        val isCameraShortcut = app.component.className == CameraActivity::class.java.name
        return FrameLayout(this).apply {
        isFocusable = true
        isClickable = true
        contentDescription = app.label
        tag = appKey(app)
        background = rounded(color(CoreColor.GROUND), dp(12).toFloat())
        foreground = tileStates()
        clipChildren = false
        clipToOutline = true
        setOnClickListener {
            if (app.component.packageName != packageName) toTelevision()
            open(Intent(Intent.ACTION_MAIN).setComponent(app.component).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
        setOnLongClickListener {
            appMenu(app)
            true
        }
        setOnKeyListener { _, keyCode, event ->
            if (keyCode != KeyEvent.KEYCODE_DPAD_CENTER && keyCode != KeyEvent.KEYCODE_ENTER) {
                return@setOnKeyListener false
            }
            when {
                event.action == KeyEvent.ACTION_DOWN && (event.isLongPress || event.repeatCount > 0) -> {
                    if (!held) appMenu(app)
                    held = true
                    true
                }
                event.action == KeyEvent.ACTION_UP && held -> {
                    held = false
                    true
                }
                else -> false
            }
        }
        setOnFocusChangeListener { target, focused ->
            // Focus is a border and a lift, not a scale. Scaling was what cut
            // the selected cards at the viewport edges on the Shield.
            target.elevation = dp(if (focused) 10 else 0).toFloat()
        }
        addView(ImageView(context).apply {
            AppMarks.open(context, mark(app)).use { setImageBitmap(BitmapFactory.decodeStream(it)) }
            scaleType = ImageView.ScaleType.FIT_CENTER
        }, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    }
    }

    private fun orderedPackages(): List<String> =
        HomeOrder.items(this).filter { it in HomeOrder.PRIMARY }

    private fun mark(app: HomeApps.App): String =
        if (app.component.className == CameraActivity::class.java.name) AppMarks.CAMERAS
        else app.component.packageName

    private fun appKey(app: HomeApps.App): String =
        if (app.component.className == CameraActivity::class.java.name) HomeOrder.CAMERAS
        else app.component.packageName

    private fun appMenu(app: HomeApps.App) {
        val order = HomeOrder.items(this)
        val key = appKey(app)
        val isCameraShortcut = key == HomeOrder.CAMERAS
        val at = order.indexOf(key)
        val actions = buildList {
            if (at > 0) add(AppAction(getString(R.string.home_move_before)) { move(key, -1) })
            if (at in 0 until order.lastIndex) add(AppAction(getString(R.string.home_move_after)) { move(key, 1) })
            if (!isCameraShortcut) {
                add(AppAction(getString(R.string.home_app_info)) {
                    open(Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS, "package:$key".toUri()))
                })
                if (key != this@HomeActivity.packageName) {
                    add(AppAction(getString(R.string.home_uninstall)) {
                        appsNeedRefresh = true
                        open(Intent(Intent.ACTION_DELETE, "package:$key".toUri()))
                    })
                }
            }
        }
        AlertDialog.Builder(this)
            .setTitle(app.label)
            .setItems(actions.map { it.label }.toTypedArray()) { _, which -> actions[which].run() }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun move(key: String, by: Int) {
        if (HomeOrder.move(this, key, by)) drawApps(key)
    }

    private fun updateClock() {
        val now = ZonedDateTime.now()
        time.text = now.format(DateTimeFormatter.ofPattern("HH:mm"))
        date.text = now.format(DateTimeFormatter.ofPattern("EEEE, d. MMMM", Locale.getDefault()))
    }

    private suspend fun refreshFacts() {
        val raw = try {
            OpusHttp.get(PlayerApp.http(this), "/api/launcher/glance")
        } catch (_: Exception) {
            return
        }
        val said = runCatching { JSONObject(raw) }.getOrNull() ?: return
        val cards = listOfNotNull(
            said.optJSONObject("outside")?.sensorFact(
                R.string.home_outside, R.drawable.ic_weather_sun, includeOutside = true),
            said.optJSONObject("living")?.sensorFact(
                R.string.home_living, R.drawable.ic_weather_home, includeOutside = false),
        )
        facts.removeAllViews()
        cards.take(MAX_FACTS).forEachIndexed { index, item ->
            if (index > 0) facts.addView(View(this).apply {
                setBackgroundColor(Color.argb(55, 138, 160, 166))
            }, LinearLayout.LayoutParams(dp(1), dp(38)))
            facts.addView(fact(item), LinearLayout.LayoutParams(
                0,
                ViewGroup.LayoutParams.MATCH_PARENT,
                if (index == 0) 1.45f else 1.05f,
            ))
        }
    }

    private fun fact(fact: Fact): View = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER
        setPadding(dp(12), 0, dp(12), 0)
        addView(ImageView(context).apply {
            setImageResource(fact.icon)
        }, LinearLayout.LayoutParams(dp(26), dp(26)).apply { marginEnd = dp(10) })
        addView(TextView(context).apply {
            text = fact.label
            setTextColor(color(CoreColor.TEXT_DIM))
            textSize = 13f
            maxLines = 1
        })
        addView(TextView(context).apply {
            text = fact.value
            setTextColor(color(CoreColor.TEXT))
            textSize = 19f
            setTypeface(typeface, Typeface.BOLD)
            maxLines = 1
            setPadding(dp(8), 0, 0, 0)
        })
        fact.humidity?.let { addView(metric(R.drawable.ic_weather_drop, it)) }
        fact.wind?.let { addView(metric(R.drawable.ic_weather_wind, it)) }
        fact.rain?.let { addView(metric(R.drawable.ic_weather_rain, it)) }
    }

    private fun metric(icon: Int, value: String): View = LinearLayout(this).apply {
        orientation = LinearLayout.HORIZONTAL
        gravity = Gravity.CENTER_VERTICAL
        setPadding(dp(10), 0, 0, 0)
        addView(ImageView(context).apply { setImageResource(icon) }, LinearLayout.LayoutParams(dp(17), dp(17)))
        addView(TextView(context).apply {
            text = value
            setTextColor(color(CoreColor.TEXT_DIM))
            textSize = 13f
            maxLines = 1
            setPadding(dp(4), 0, 0, 0)
        })
    }

    private fun JSONObject.sensorFact(label: Int, icon: Int, includeOutside: Boolean): Fact? {
        val temperature = number("temperature_c") ?: return null
        return Fact(
            icon = icon,
            label = getString(label),
            value = getString(R.string.home_temperature, number(temperature, 1)),
            humidity = number("humidity_pct")?.let { getString(R.string.home_humidity_value, number(it, 0)) },
            wind = if (includeOutside) number("wind_kmh")?.let {
                getString(R.string.home_wind_value, number(it, 0))
            } else null,
            rain = if (includeOutside) number("rain_mm")?.let {
                getString(R.string.home_rain_value, number(it, 1))
            } else null,
        )
    }

    private fun JSONObject.number(name: String): Double? =
        if (isNull(name) || !has(name)) null else optDouble(name).takeUnless(Double::isNaN)

    private fun number(value: Double, decimals: Int): String = NumberFormat.getNumberInstance().apply {
        minimumFractionDigits = 0
        maximumFractionDigits = decimals
    }.format(value)

    // Another app's sound comes out of the Shield's HDMI, so the receiver has to
    // be on that input; left on the DAC's, the app plays in silence. Asked again
    // for a while, because a server being redeployed is gone for seconds and the
    // app it was asked for is already on the screen by then.
    private fun toTelevision() {
        val app = applicationContext
        lifecycleScope.launch {
            repeat(RECEIVER_TRIES) { attempt ->
                try {
                    OpusHttp.post(PlayerApp.http(app), "/api/tv/video")
                    return@launch
                } catch (_: Exception) {
                    if (attempt < RECEIVER_TRIES - 1) delay(RECEIVER_PAUSE_MS)
                }
            }
            Toast.makeText(app, R.string.home_receiver_failed, Toast.LENGTH_LONG).show()
        }
    }

    private fun open(intent: Intent) {
        try {
            startActivity(intent)
        } catch (_: RuntimeException) {
            Toast.makeText(this, R.string.home_unavailable, Toast.LENGTH_LONG).show()
        }
    }

    private fun tileStates() = StateListDrawable().apply {
        addState(
            intArrayOf(android.R.attr.state_focused),
            rounded(Color.TRANSPARENT, dp(12).toFloat(), dp(3), color(CoreColor.ACCENT)),
        )
        addState(
            intArrayOf(),
            rounded(Color.TRANSPARENT, dp(12).toFloat(), dp(1), Color.argb(65, 138, 160, 166)),
        )
    }

    private fun rounded(fill: Int, radius: Float, stroke: Int = 0, strokeColor: Int = Color.TRANSPARENT) =
        GradientDrawable().apply {
            setColor(fill)
            cornerRadius = radius
            if (stroke > 0) setStroke(stroke, strokeColor)
        }

    private fun color(which: CoreColor): Int = ContextCompat.getColor(this, which.resource)

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).roundToInt()

    private data class Fact(
        val icon: Int,
        val label: String,
        val value: String,
        val humidity: String?,
        val wind: String?,
        val rain: String?,
    )
    private data class AppAction(val label: String, val run: () -> Unit)

    private enum class CoreColor(val resource: Int) {
        BG(biz.boskovic.opus.core.R.color.opus_bg),
        GROUND(biz.boskovic.opus.core.R.color.opus_ground),
        ACCENT(biz.boskovic.opus.core.R.color.opus_accent),
        TEXT(biz.boskovic.opus.core.R.color.opus_text),
        TEXT_DIM(biz.boskovic.opus.core.R.color.opus_text_dim),
    }

    companion object {
        private const val TILES_PER_ROW = 4
        /** One size for every door, 16:9 like the marks, so nothing is stretched. */
        private const val TILE_WIDTH_DP = 160
        private const val TILE_HEIGHT_DP = 90
        private const val MAX_FACTS = 2
        private const val RECEIVER_TRIES = 5
        private const val RECEIVER_PAUSE_MS = 3_000L
        private const val CLOCK_REFRESH_MS = 30_000L
        private const val GLANCE_REFRESH_MS = 5 * 60_000L
    }
}
