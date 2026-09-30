package biz.boskovic.opus.music

import android.Manifest
import android.content.pm.PackageManager
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import biz.boskovic.opus.core.R as CoreR
import biz.boskovic.opus.core.Updater
import java.io.IOException
import kotlinx.coroutines.launch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONException

class SetupActivity : ComponentActivity() {
    private val updater by lazy { Updater(this, Car.client(this), "/api/app/music.json", "/api/app/opus-music.apk") }
    private val notifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (!granted) Log.i(TAG, "notifications declined; updates are offered here only")
    }

    private lateinit var status: TextView
    private lateinit var cacheUsage: TextView
    private lateinit var update: TextView
    private lateinit var install: Button
    private lateinit var clearCache: Button
    private lateinit var cacheFavorites: Button
    private lateinit var chooseAlbums: Button
    private lateinit var cacheAlbums: Button
    private lateinit var dataSaver: CheckBox

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_setup)
        val username = findViewById<EditText>(R.id.username)
        val password = findViewById<EditText>(R.id.password)
        val connect = findViewById<Button>(R.id.connect)
        status = findViewById(R.id.status)
        cacheUsage = findViewById(R.id.cache_usage)
        update = findViewById(R.id.update)
        install = findViewById(R.id.install)
        clearCache = findViewById(R.id.clear_cache)
        cacheFavorites = findViewById(R.id.cache_favorites)
        chooseAlbums = findViewById(R.id.choose_albums)
        cacheAlbums = findViewById(R.id.cache_albums)
        dataSaver = findViewById(R.id.data_saver)
        dataSaver.setOnCheckedChangeListener { _, enabled ->
            if (Car.savesData(this) != enabled) Car.setSavesData(this, enabled)
        }

        connect.setOnClickListener {
            connect.isEnabled = false
            status.text = ""
            lifecycleScope.launch {
                try {
                    Car.pair(this@SetupActivity, username.text.toString().trim(), password.text.toString())
                    password.text.clear()
                    show()
                    askForNotifications()
                } catch (_: BadCredentials) {
                    status.setText(R.string.setup_bad_credentials)
                } catch (failure: IOException) {
                    status.text = getString(R.string.setup_failed, failure.message)
                } catch (failure: JSONException) {
                    status.text = getString(R.string.setup_failed, failure.message)
                } finally {
                    connect.isEnabled = true
                }
            }
        }
        clearCache.setOnClickListener {
            setCacheControlsEnabled(false)
            lifecycleScope.launch {
                try {
                    // Removing spans can touch many small files, so it must
                    // not block the screen that lets somebody reconnect their
                    // phone.
                    withContext(Dispatchers.IO) { ListeningCache.clear(this@SetupActivity) }
                    status.setText(R.string.cache_cleared)
                    showCacheUsage()
                } catch (failure: Exception) {
                    Log.w(TAG, "could not clear the music cache", failure)
                    status.text = getString(R.string.cache_clear_failed, failure.message)
                } finally {
                    setCacheControlsEnabled(true)
                }
            }
        }
        cacheFavorites.setOnClickListener {
            setCacheControlsEnabled(false)
            lifecycleScope.launch {
                try {
                    val count = ListeningCache.cacheFavorites(this@SetupActivity) { done, total ->
                        if (!isFinishing && !isDestroyed) {
                            status.text = getString(R.string.cache_favorites_progress, done, total)
                        }
                    }
                    status.text = resources.getQuantityString(
                        R.plurals.cache_favorites_done, count, count,
                    )
                    showCacheUsage()
                } catch (failure: Exception) {
                    Log.w(TAG, "could not cache favorite music", failure)
                    status.text = getString(R.string.cache_favorites_failed, failure.message)
                } finally {
                    setCacheControlsEnabled(true)
                }
            }
        }
        chooseAlbums.setOnClickListener {
            startActivity(Intent(this, OfflineActivity::class.java))
        }
        cacheAlbums.setOnClickListener {
            setCacheControlsEnabled(false)
            lifecycleScope.launch {
                try {
                    val count = ListeningCache.cacheAlbums(this@SetupActivity) { done, total ->
                        if (!isFinishing && !isDestroyed) {
                            status.text = getString(R.string.cache_albums_progress, done, total)
                        }
                    }
                    status.text = resources.getQuantityString(
                        R.plurals.cache_albums_done, count, count,
                    )
                    showCacheUsage()
                } catch (failure: Exception) {
                    Log.w(TAG, "could not cache selected albums", failure)
                    status.text = getString(R.string.cache_albums_failed, failure.message)
                } finally {
                    setCacheControlsEnabled(true)
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        show()
        lifecycleScope.launch { offer() }
    }

    private fun show() {
        status.text = try {
            when {
                Car.token(this) == null -> {
                    clearCache.visibility = View.GONE
                    cacheFavorites.visibility = View.GONE
                    chooseAlbums.visibility = View.GONE
                    cacheAlbums.visibility = View.GONE
                    cacheUsage.visibility = View.GONE
                    dataSaver.visibility = View.GONE
                    ""
                }
                Car.refused(this) -> {
                    clearCache.visibility = View.GONE
                    cacheFavorites.visibility = View.GONE
                    chooseAlbums.visibility = View.GONE
                    cacheAlbums.visibility = View.GONE
                    cacheUsage.visibility = View.GONE
                    dataSaver.visibility = View.GONE
                    getString(R.string.car_refused)
                }
                else -> {
                    clearCache.visibility = View.VISIBLE
                    cacheFavorites.visibility = View.VISIBLE
                    chooseAlbums.visibility = View.VISIBLE
                    cacheAlbums.visibility = View.VISIBLE
                    cacheAlbums.isEnabled = OfflineAlbums.all(this).isNotEmpty()
                    cacheUsage.visibility = View.VISIBLE
                    dataSaver.visibility = View.VISIBLE
                    dataSaver.isChecked = Car.savesData(this)
                    showCacheUsage()
                    getString(R.string.setup_connected)
                }
            }
        } catch (unreadable: VaultUnavailable) {
            Log.w(TAG, "the car token could not be read", unreadable)
            clearCache.visibility = View.GONE
            cacheFavorites.visibility = View.GONE
            chooseAlbums.visibility = View.GONE
            cacheAlbums.visibility = View.GONE
            cacheUsage.visibility = View.GONE
            dataSaver.visibility = View.GONE
            getString(R.string.car_vault_unavailable)
        }
    }

    private fun showCacheUsage() {
        lifecycleScope.launch {
            val used = withContext(Dispatchers.IO) { ListeningCache.usedBytes(this@SetupActivity) }
            cacheUsage.text = getString(
                R.string.cache_usage,
                used / (1024 * 1024),
                ListeningCache.capacityBytes() / (1024 * 1024),
            )
        }
    }

    /** Cache eviction and cache writes both mutate Media3's index. Keeping one
     * operation at a time avoids a misleading successful completion while the
     * other action has just removed its spans. */
    private fun setCacheControlsEnabled(enabled: Boolean) {
        clearCache.isEnabled = enabled
        cacheFavorites.isEnabled = enabled
        chooseAlbums.isEnabled = enabled
        cacheAlbums.isEnabled = enabled && OfflineAlbums.all(this).isNotEmpty()
    }

    private suspend fun offer() {
        val offered = try {
            updater.offer()
        } catch (failure: IOException) {
            Log.w(TAG, "update check failed", failure)
            null
        } ?: return
        update.visibility = View.VISIBLE
        update.setText(R.string.update_ready)
        install.visibility = View.VISIBLE
        install.setOnClickListener {
            install.isEnabled = false
            lifecycleScope.launch {
                try {
                    updater.install(this@SetupActivity, updater.download(offered))
                } catch (failure: IOException) {
                    update.text = getString(CoreR.string.update_failed, failure.message)
                } finally {
                    install.isEnabled = true
                }
            }
        }
    }

    private fun askForNotifications() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            notifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }

    private companion object {
        const val TAG = "OpusMusicSetup"
    }
}
