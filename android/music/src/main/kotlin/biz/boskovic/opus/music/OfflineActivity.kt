package biz.boskovic.opus.music

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import biz.boskovic.opus.core.OpusHttp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** Phone-only chooser for albums that should survive a journey without data.
 * Android Auto remains a playback surface; choosing and downloading a whole
 * library while driving would be both unsafe and difficult to make clear. */
class OfflineActivity : ComponentActivity() {
    private lateinit var title: TextView
    private lateinit var status: TextView
    private lateinit var entries: LinearLayout

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val padding = (24 * resources.displayMetrics.density).toInt()
        entries = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        title = TextView(this).apply { textSize = 24f }
        status = TextView(this)
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
            addView(title)
            addView(status)
            addView(entries)
        }
        setContentView(ScrollView(this).apply { addView(body) })
        showArtists()
    }

    private fun showArtists() {
        heading(R.string.offline_choose_artist)
        addButton(R.string.offline_selected) { showSelected() }
        lifecycleScope.launch {
            try {
                val artists = withContext(Dispatchers.IO) {
                    JSONArray(OpusHttp.get(Car.client(this@OfflineActivity), "/api/library/music?order=title"))
                }
                for (at in 0 until artists.length()) {
                    val artist = artists.getJSONObject(at)
                    addButton(artist.getString("title")) {
                        showReleases(artist.getLong("id"), artist.getString("title"))
                    }
                }
            } catch (failure: Exception) {
                status.text = getString(R.string.offline_load_failed, failure.message)
            }
        }
    }

    private fun showReleases(artistId: Long, artist: String) {
        heading(getString(R.string.offline_choose_release, artist))
        addButton(R.string.offline_back) { showArtists() }
        lifecycleScope.launch {
            try {
                val releases = withContext(Dispatchers.IO) {
                    JSONObject(OpusHttp.get(Car.client(this@OfflineActivity), "/api/library/artist/$artistId"))
                        .getJSONArray("releases")
                }
                for (at in 0 until releases.length()) {
                    val release = releases.getJSONObject(at)
                    val id = release.getLong("id")
                    val label = release.getString("title") + release.optString("year").takeIf { it.isNotEmpty() }
                        ?.let { " ($it)" }.orEmpty()
                    val saved = OfflineAlbums.find(this@OfflineActivity, id) != null
                    addButton(if (saved) getString(R.string.offline_remove, label) else getString(R.string.offline_add, label)) {
                        lifecycleScope.launch {
                            try {
                                if (saved) {
                                    OfflineAlbums.remove(this@OfflineActivity, id)
                                } else {
                                    status.text = getString(R.string.offline_loading_release, label)
                                    OfflineAlbums.add(this@OfflineActivity, id, release.getString("title"), artist)
                                }
                                showReleases(artistId, artist)
                            } catch (failure: Exception) {
                                status.text = getString(R.string.offline_load_failed, failure.message)
                            }
                        }
                    }
                }
            } catch (failure: Exception) {
                status.text = getString(R.string.offline_load_failed, failure.message)
            }
        }
    }

    private fun showSelected() {
        heading(R.string.offline_selected)
        addButton(R.string.offline_back) { showArtists() }
        val albums = OfflineAlbums.all(this)
        if (albums.isEmpty()) status.setText(R.string.offline_none_selected)
        for (album in albums) {
            addButton(getString(R.string.offline_remove, album.title)) {
                OfflineAlbums.remove(this, album.id)
                showSelected()
            }
        }
    }

    private fun heading(text: Int) = heading(getString(text))

    private fun heading(text: String) {
        title.text = text
        status.text = ""
        entries.removeAllViews()
    }

    private fun addButton(text: Int, action: () -> Unit) = addButton(getString(text), action)

    private fun addButton(text: String, action: () -> Unit) {
        entries.addView(Button(this).apply {
            this.text = text
            setOnClickListener { action() }
        })
    }
}
