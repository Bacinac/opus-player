package biz.boskovic.opus.core

import android.content.Context
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import androidx.core.content.pm.PackageInfoCompat
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl

object Opus {
    val origin: HttpUrl = BuildConfig.OPUS_ORIGIN.toHttpUrl()

    val site: String = with(origin) {
        if (port == HttpUrl.defaultPort(scheme)) "$scheme://$host" else "$scheme://$host:$port"
    }

    fun url(path: String): String = origin.resolve(path)?.toString()
        ?: throw IllegalArgumentException("not a path on ${origin.host}: $path")

    fun ours(url: HttpUrl): Boolean =
        url.isHttps && url.host == origin.host && url.port == origin.port

    fun ours(url: Uri): Boolean = ours(url.toString())

    fun ours(url: String): Boolean = url.toHttpUrlOrNull()?.let(::ours) ?: false

    fun packageInfo(context: Context, flags: Int = 0): PackageInfo =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.packageManager.getPackageInfo(context.packageName, PackageManager.PackageInfoFlags.of(flags.toLong()))
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageInfo(context.packageName, flags)
        }

    fun archiveInfo(context: Context, path: String, flags: Int): PackageInfo? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            context.packageManager.getPackageArchiveInfo(path, PackageManager.PackageInfoFlags.of(flags.toLong()))
        } else {
            @Suppress("DEPRECATION")
            context.packageManager.getPackageArchiveInfo(path, flags)
        }

    fun versionCode(context: Context): Long = PackageInfoCompat.getLongVersionCode(packageInfo(context))

    fun versionName(context: Context): String = packageInfo(context).versionName.orEmpty()

    fun userAgent(context: Context): String =
        "OPUS-${context.packageName.substringAfterLast('.')}/${versionName(context)}"

    private fun String.toHttpUrlOrNull(): HttpUrl? = runCatching { toHttpUrl() }.getOrNull()
}
