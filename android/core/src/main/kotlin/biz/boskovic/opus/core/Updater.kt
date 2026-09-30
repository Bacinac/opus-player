package biz.boskovic.opus.core

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import androidx.core.content.FileProvider
import androidx.core.content.pm.PackageInfoCompat
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONException
import org.json.JSONObject

class UpdateRejected(message: String) : IOException(message)

/** The app as the Player's own shelf serves it: `meta` says which version is
 *  there, `apk` is the file. What arrives is installed only when its digest,
 *  package, version and signer all match. */
class Updater(
    private val context: Context,
    private val client: OkHttpClient,
    private val meta: String,
    private val apk: String,
) {
    class Offer(val versionCode: Long, val sha256: String)

    suspend fun offer(): Offer? {
        val said = OpusHttp.get(client, meta)
        val offer = try {
            JSONObject(said).let { Offer(it.getLong("versionCode"), it.getString("sha256").lowercase()) }
        } catch (bad: JSONException) {
            throw UpdateRejected("$meta is not a version: ${bad.message}")
        }
        return offer.takeIf { it.versionCode > Opus.versionCode(context) }
    }

    suspend fun download(offer: Offer): File = withContext(Dispatchers.IO) {
        val file = File(File(context.cacheDir, "updates").apply { mkdirs() }, "update.apk")
        val request = Request.Builder().url(Opus.url("$apk?v=${offer.versionCode}")).build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw IOException("HTTP ${response.code} from $apk")
            file.outputStream().use { out -> response.body.byteStream().copyTo(out) }
        }
        try {
            verify(file, offer)
        } catch (rejected: UpdateRejected) {
            file.delete()
            throw rejected
        }
        file
    }

    fun install(activity: Activity, file: File) {
        val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.updates", file)
        try {
            activity.startActivity(
                Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "application/vnd.android.package-archive")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            )
        } catch (refused: RuntimeException) {
            throw IOException("the installer could not be opened: ${refused.message}", refused)
        }
    }

    private fun verify(file: File, offer: Offer) {
        val installed = Opus.packageInfo(context, PackageManager.GET_SIGNING_CERTIFICATES)
        verify(offer, meta, sha256(file), Apk(installed)) {
            Opus.archiveInfo(context, file.path, PackageManager.GET_SIGNING_CERTIFICATES)?.let { Apk(it) }
        }
    }

    class Apk(val name: String, val versionCode: Long, val signers: Set<String>) {
        constructor(info: PackageInfo) : this(
            info.packageName,
            PackageInfoCompat.getLongVersionCode(info),
            info.signingInfo?.apkContentsSigners.orEmpty().map { it.toCharsString() }.toSet(),
        )
    }

    companion object {
        internal fun verify(offer: Offer, meta: String, digest: String, installed: Apk, archive: () -> Apk?) {
            if (digest != offer.sha256) throw UpdateRejected("digest does not match $meta")
            val arrived = archive() ?: throw UpdateRejected("not a readable package")
            if (arrived.name != installed.name) {
                throw UpdateRejected("package ${arrived.name} is not ${installed.name}")
            }
            if (arrived.versionCode != offer.versionCode) {
                throw UpdateRejected("package is version ${arrived.versionCode}, not ${offer.versionCode}")
            }
            if (arrived.signers.isEmpty() || arrived.signers != installed.signers) {
                throw UpdateRejected("package is not signed by this app's key")
            }
        }

        internal fun sha256(file: File): String {
            val digest = MessageDigest.getInstance("SHA-256")
            file.inputStream().use { input ->
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
            return digest.digest().joinToString("") { "%02x".format(it) }
        }
    }
}
