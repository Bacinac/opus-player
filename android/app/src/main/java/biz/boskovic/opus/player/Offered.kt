package biz.boskovic.opus.player

import android.content.ContentResolver
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.os.Build
import android.util.Log
import android.util.Size
import biz.boskovic.opus.core.Opus
import java.io.IOException

/** What another app shared, split into what may be sent and what may not. */
object Offered {
    private const val TAG = "OpusOffered"
    private const val THUMBNAILS = 12

    class Sorted(val accepted: List<Uri>, val refused: Int, val thumbnails: List<Bitmap>)

    /** Only a photograph or a video another app's provider vouches for. A file
     *  path, or a provider of this app, would be read with this app's own rights. */
    fun admits(scheme: String?, authority: String?, type: String?, own: Set<String>): Boolean =
        scheme == ContentResolver.SCHEME_CONTENT &&
            !authority.isNullOrEmpty() && authority.substringAfterLast('@') !in own &&
            type != null && (type.startsWith("image/") || type.startsWith("video/"))

    fun sort(context: Context, offered: List<Uri>): Sorted {
        val own = Opus.packageInfo(context, PackageManager.GET_PROVIDERS).providers.orEmpty()
            .flatMap { it.authority.orEmpty().split(';') }
            .toSet()
        val (accepted, refused) = offered.distinct().partition { uri ->
            admits(uri.scheme, uri.authority, typeOf(context, uri), own).also { taken ->
                if (!taken) Log.w(TAG, "refused a shared item from ${uri.scheme}://${uri.authority}")
            }
        }
        return Sorted(accepted, refused.size, accepted.take(THUMBNAILS).mapNotNull { thumbnail(context, it) })
    }

    /** Another app's provider says no, or fails, with unchecked exceptions of
     *  its own choosing. */
    private fun typeOf(context: Context, uri: Uri): String? {
        if (uri.scheme != ContentResolver.SCHEME_CONTENT) return null
        return try {
            context.contentResolver.getType(uri)
        } catch (denied: RuntimeException) {
            Log.w(TAG, "${uri.authority} would not say what it shared", denied)
            null
        }
    }

    private fun thumbnail(context: Context, uri: Uri): Bitmap? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        return try {
            context.contentResolver.loadThumbnail(uri, Size(240, 240), null)
        } catch (unreadable: IOException) {
            Log.w(TAG, "no thumbnail from ${uri.authority}", unreadable)
            null
        } catch (unreadable: RuntimeException) {
            Log.w(TAG, "no thumbnail from ${uri.authority}", unreadable)
            null
        }
    }
}
