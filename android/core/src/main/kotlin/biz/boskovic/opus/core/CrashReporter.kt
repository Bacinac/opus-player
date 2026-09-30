package biz.boskovic.opus.core

import android.app.Application
import android.content.Context
import android.os.Build
import android.util.Log
import java.io.File
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject

/** The dying process only writes, synchronously, and hands the crash on to the
 *  previous handler; the next start sends the file to /api/app/crash-report. */
object CrashReporter {
    private const val TAG = "OpusCrash"
    private const val FILE = "crash-report.json"

    fun install(app: Application) {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            try {
                write(app, thread, error)
            } catch (failure: Throwable) {
                Log.e(TAG, "crash report could not be written", failure)
            }
            previous?.uncaughtException(thread, error)
        }
    }

    private fun write(context: Context, thread: Thread, error: Throwable) {
        val body = JSONObject()
            .put("app", context.packageName)
            .put("version", Opus.versionName(context))
            .put("thread", thread.name)
            .put("stack", Log.getStackTraceString(error).take(8000))
            .put("occurred_at_ms", System.currentTimeMillis())
            .put("device", "${Build.MANUFACTURER} ${Build.MODEL} / Android ${Build.VERSION.RELEASE}")
        File(context.filesDir, FILE).writeText(body.toString())
    }

    /** A 401 keeps the file for a start that has a credential; any other 4xx is
     *  a report the server will never take, so it is dropped. */
    fun flush(context: Context, client: OkHttpClient) {
        val file = File(context.applicationContext.filesDir, FILE)
        if (!file.exists()) return
        Thread {
            val request = Request.Builder()
                .url(Opus.url("/api/app/crash-report"))
                .post(file.readText().toRequestBody("application/json; charset=utf-8".toMediaType()))
                .build()
            try {
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful || (response.code in 400..499 && response.code != 401)) {
                        file.delete()
                    }
                    if (!response.isSuccessful) Log.w(TAG, "crash report refused: HTTP ${response.code}")
                }
            } catch (failure: java.io.IOException) {
                Log.w(TAG, "crash report not sent", failure)
            }
        }.start()
    }
}
