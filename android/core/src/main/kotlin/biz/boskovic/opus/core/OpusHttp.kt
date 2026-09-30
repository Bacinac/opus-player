package biz.boskovic.opus.core

import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response

class Refused(val code: Int, what: String) : IOException("HTTP $code from $what")

/** Installed as a network interceptor, so every redirect hop is judged on its
 *  own: a credential leaves this app only for the OPUS origin over https. */
class Credentials(
    private val agent: String,
    private val ours: (HttpUrl) -> Boolean = Opus::ours,
    private val credential: () -> Pair<String, String>?,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val sent = request.newBuilder()
        if (ours(request.url)) {
            sent.header("User-Agent", agent)
            credential()?.let { (name, value) -> sent.header(name, value) }
        } else {
            sent.removeHeader("Authorization").removeHeader("Cookie")
        }
        return chain.proceed(sent.build())
    }
}

object OpusHttp {
    private val base: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    fun client(agent: String, credential: () -> Pair<String, String>?): OkHttpClient =
        base.newBuilder()
            .addNetworkInterceptor(Credentials(agent, credential = credential))
            .build()

    suspend fun text(client: OkHttpClient, request: Request): String = withContext(Dispatchers.IO) {
        client.newCall(request).execute().use { response ->
            val what = request.url.encodedPath
            when {
                response.code == 401 || response.code == 403 -> throw Refused(response.code, what)
                !response.isSuccessful -> throw IOException("HTTP ${response.code} from $what")
                else -> response.body.string()
            }
        }
    }

    suspend fun get(client: OkHttpClient, path: String): String =
        text(client, Request.Builder().url(Opus.url(path)).build())

    suspend fun post(client: OkHttpClient, path: String): String =
        text(client, Request.Builder().url(Opus.url(path)).post(ByteArray(0).toRequestBody()).build())
}
