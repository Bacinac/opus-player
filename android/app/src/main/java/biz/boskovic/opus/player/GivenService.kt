package biz.boskovic.opus.player

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.provider.OpenableColumns
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.core.content.IntentCompat
import biz.boskovic.opus.core.Opus
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import okhttp3.Call
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody
import okio.BufferedSink
import okio.source
import org.json.JSONException
import org.json.JSONObject

/** Photographs the phone's gallery handed to OPUS, sent in the foreground with
 *  the person's own cookie. The library decides everything about what arrives. */
class GivenService : Service() {

    data class Told(val sent: Int, val known: Int, val failed: Int)

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    @Volatile private var stopped = false
    @Volatile private var sending: Call? = null

    override fun onBind(intent: Intent): IBinder? = null

    override fun onStartCommand(intent: Intent, flags: Int, startId: Int): Int {
        val pictures = IntentCompat.getParcelableArrayListExtra(intent, PICTURES, Uri::class.java).orEmpty()
        val manager = getSystemService(NotificationManager::class.java)
        manager.createNotificationChannel(
            NotificationChannel(CHANNEL, getString(R.string.given_channel), NotificationManager.IMPORTANCE_LOW)
        )
        try {
            ServiceCompat.startForeground(
                this,
                NOTICE,
                progress(0, pictures.size),
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0,
            )
        } catch (refused: IllegalStateException) {
            Log.e(TAG, "the system did not let the upload run", refused)
            finish(manager, Told(0, 0, pictures.size), startId)
            return START_NOT_STICKY
        }
        scope.launch {
            val told = send(pictures) { done -> manager.notify(NOTICE, progress(done, pictures.size)) }
            if (!stopped) ServiceCompat.stopForeground(this@GivenService, ServiceCompat.STOP_FOREGROUND_DETACH)
            finish(manager, told, startId)
        }
        return START_NOT_STICKY
    }

    private fun finish(manager: NotificationManager, told: Told, startId: Int) {
        results.value = told
        manager.notify(
            NOTICE,
            NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_upload_done)
                .setContentTitle(getString(R.string.given_channel))
                .setContentText(getString(R.string.given_done, told.sent, told.known, told.failed))
                .build(),
        )
        stopSelf(startId)
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        Log.w(TAG, "upload stopped by the system's time limit")
        stopped = true
        sending?.cancel()
        stopSelf()
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private fun progress(done: Int, of: Int): Notification =
        NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_upload)
            .setContentTitle(getString(R.string.given_channel))
            .setContentText(getString(R.string.given_progress, done + 1, of))
            .setProgress(of, done, false)
            .setOngoing(true)
            .build()

    private fun send(pictures: List<Uri>, onEach: (Int) -> Unit): Told {
        val client = PlayerApp.http(this).newBuilder()
            .writeTimeout(10, TimeUnit.MINUTES)
            .readTimeout(10, TimeUnit.MINUTES)
            .build()
        var sent = 0
        var known = 0
        var failed = 0
        for ((index, picture) in pictures.withIndex()) {
            if (stopped) return Told(sent, known, failed + pictures.size - index)
            onEach(index)
            try {
                val request = Request.Builder()
                    .url(Opus.url("/api/photos/offer?name=${Uri.encode(nameOf(picture))}"))
                    .post(stream(picture))
                    .build()
                client.newCall(request).also { sending = it }.execute().use { response ->
                    if (!response.isSuccessful) throw IOException("HTTP ${response.code} from /api/photos/offer")
                    if (JSONObject(response.body.string()).optBoolean("known")) known++ else sent++
                }
            } catch (failure: IOException) {
                Log.w(TAG, "$picture was not sent", failure)
                failed++
            } catch (failure: JSONException) {
                Log.w(TAG, "$picture got an answer that is not JSON", failure)
                failed++
            } finally {
                sending = null
            }
        }
        return Told(sent, known, failed)
    }

    private fun stream(picture: Uri) = object : RequestBody() {
        override fun contentType(): MediaType = "application/octet-stream".toMediaType()

        override fun writeTo(sink: BufferedSink) {
            val input = provided(picture) { contentResolver.openInputStream(picture) }
                ?: throw IOException("nothing to read at $picture")
            input.source().use { sink.writeAll(it) }
        }
    }

    private fun nameOf(picture: Uri): String =
        provided(picture) {
            contentResolver.query(picture, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { row ->
                if (row.moveToFirst() && !row.isNull(0)) row.getString(0) else null
            }
        } ?: picture.lastPathSegment ?: "photograph"

    /** Another app's provider says no, or fails, with unchecked exceptions of
     *  its own choosing; to the upload each is one photograph that could not be read. */
    private inline fun <T> provided(picture: Uri, read: () -> T): T =
        try {
            read()
        } catch (failure: RuntimeException) {
            throw IOException("$picture could not be read from the app that shared it", failure)
        }

    companion object {
        private const val TAG = "OpusGiven"
        private const val CHANNEL = "given"
        private const val NOTICE = 1
        private const val PICTURES = "pictures"

        private val results = MutableStateFlow<Told?>(null)
        val told: StateFlow<Told?> get() = results

        fun heard() {
            results.value = null
        }

        /** What a share intent carried, whether one or many; null when it is not a share. */
        fun of(intent: Intent): List<Uri>? = when (intent.action) {
            Intent.ACTION_SEND ->
                listOfNotNull(IntentCompat.getParcelableExtra(intent, Intent.EXTRA_STREAM, Uri::class.java))
            Intent.ACTION_SEND_MULTIPLE ->
                IntentCompat.getParcelableArrayListExtra(intent, Intent.EXTRA_STREAM, Uri::class.java).orEmpty()
            else -> null
        }

        /** The read grant travels with the service intent, so it lasts as long
         *  as the upload rather than as long as the activity that received it. */
        fun start(context: Context, pictures: List<Uri>) {
            val clip = ClipData.newRawUri("", pictures.first()).apply {
                pictures.drop(1).forEach { addItem(ClipData.Item(it)) }
            }
            val work = Intent(context, GivenService::class.java)
                .putParcelableArrayListExtra(PICTURES, ArrayList(pictures))
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            work.clipData = clip
            ContextCompat.startForegroundService(context, work)
        }
    }
}
