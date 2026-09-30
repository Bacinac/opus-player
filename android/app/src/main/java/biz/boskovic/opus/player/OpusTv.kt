package biz.boskovic.opus.player

import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import biz.boskovic.opus.core.Opus
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONArray
import org.json.JSONException

/** What the page can ask of the box it is running on.
 *
 * A WebView injects this object into every frame of every origin. It answers
 * only a caller holding the key of [Bridge]. */
class OpusTv(private val host: PlayerActivity, private val engine: Engine) {

    private val secret = Bridge.Key()

    /** False when this WebView cannot run a document-start script; then the
     *  page gets no bridge at all. */
    fun attach(web: WebView): Boolean {
        if (!WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) return false
        web.addJavascriptInterface(this, Bridge.NAME)
        WebViewCompat.addDocumentStartJavaScript(web, secret.script(), Bridge.origins())
        return true
    }

    private fun admit(given: String) {
        if (!secret.opens(given)) {
            Log.e(TAG, "the bridge was called by a frame that is not the OPUS page")
            throw SecurityException("the bridge answers only the OPUS page")
        }
    }

    private fun refuse(why: String): Nothing {
        Log.e(TAG, why)
        throw IllegalArgumentException(why)
    }

    private fun ours(url: String): String {
        if (!Opus.ours(url)) {
            refuse("refused an address outside ${Opus.site}: ${url.toHttpUrlOrNull()?.host ?: url.substringBefore(':')}")
        }
        return url
    }

    private fun sidecars(raw: String): List<Engine.Sidecar> {
        if (raw.isBlank()) return emptyList()
        return try {
            val list = JSONArray(raw)
            (0 until list.length()).map { i ->
                val entry = list.getJSONObject(i)
                Engine.Sidecar(ours(entry.getString("url")), entry.optString("lang"), entry.optString("label"))
            }
        } catch (malformed: JSONException) {
            refuse("the subtitles are not a list of tracks: ${malformed.message}")
        }
    }

    @JavascriptInterface
    fun engine(key: String): String {
        admit(key)
        return "media3"
    }

    @JavascriptInterface
    fun quit(key: String) {
        admit(key)
        host.runOnUiThread { host.finishAffinity() }
    }

    @JavascriptInterface
    fun version(key: String): Long {
        admit(key)
        return Opus.versionCode(host)
    }

    @JavascriptInterface
    fun probe(key: String): String {
        admit(key)
        return Box.describe(host)
    }

    /** The server needs this answer before it chooses direct play. It is kept
     * separate from [probe] because the media dimensions are known only after
     * the page asks the catalogue for the selected title. */
    @JavascriptInterface
    fun canVideo(key: String, codec: String, width: Int, height: Int): Boolean {
        admit(key)
        return Box.hardwareDecodesVideo(codec, width, height)
    }

    @JavascriptInterface
    fun play(
        key: String,
        url: String,
        startSeconds: Double,
        subs: String,
        audio: String,
        text: String,
        frameRate: Double,
    ) {
        admit(key)
        val source = ours(url)
        val tracks = sidecars(subs)
        host.runOnUiThread {
            engine.open(source, startSeconds, tracks, audio, text, frameRate.toFloat())
            if (!host.forward()) engine.unseen()
        }
    }

    @JavascriptInterface
    fun plugged(key: String): String {
        admit(key)
        return Box.plugged(host)
    }

    @JavascriptInterface
    fun describe(key: String, title: String, artist: String, album: String, art: String) {
        admit(key)
        host.runOnUiThread { engine.describe(title, artist, album, art) }
    }

    @JavascriptInterface
    fun toggle(key: String) {
        admit(key)
        host.runOnUiThread { engine.toggle() }
    }

    @JavascriptInterface
    fun seek(key: String, seconds: Double) {
        admit(key)
        host.runOnUiThread { engine.seek(seconds) }
    }

    @JavascriptInterface
    fun stop(key: String) {
        admit(key)
        host.runOnUiThread { engine.stop() }
    }

    @JavascriptInterface
    fun captionsUp(key: String, raised: Boolean) {
        admit(key)
        host.runOnUiThread { engine.raiseCaptions(raised) }
    }

    @JavascriptInterface
    fun state(key: String): String {
        admit(key)
        return engine.state()
    }

    @JavascriptInterface
    fun chooseAudio(key: String, index: Int) {
        admit(key)
        host.runOnUiThread { engine.choose(Engine.AUDIO, index) }
    }

    @JavascriptInterface
    fun chooseText(key: String, index: Int) {
        admit(key)
        host.runOnUiThread { engine.choose(Engine.TEXT, index) }
    }

    @JavascriptInterface
    fun awake(key: String, on: Boolean) {
        admit(key)
        host.runOnUiThread { host.awake(on) }
    }

    @JavascriptInterface
    fun hears(key: String): Boolean {
        admit(key)
        return host.hearing.possible()
    }

    @JavascriptInterface
    fun listen(key: String, language: String) {
        admit(key)
        host.runOnUiThread { host.listen(language) }
    }

    @JavascriptInterface
    fun stopListening(key: String) {
        admit(key)
        host.runOnUiThread { host.hearing.stop() }
    }

    @JavascriptInterface
    fun voiceKey(key: String, taken: Boolean) {
        admit(key)
        host.hearing.wanted = taken
    }

    private companion object {
        const val TAG = "OpusTv"
    }
}
