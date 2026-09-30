package biz.boskovic.opus.music

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.core.content.edit
import biz.boskovic.opus.core.Opus
import biz.boskovic.opus.core.OpusHttp
import java.io.IOException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.UUID
import org.json.JSONObject

class NotPaired : IOException("this phone is not paired")

class BadCredentials : IOException("bad credentials")

class VaultUnavailable(cause: Throwable) : IOException("the car token cannot be sealed or opened right now: ${cause.message}", cause)

object Car {
    private const val TAG = "OpusCar"
    private const val PREFS = "opus_car"
    private const val CACHE_SCOPE = "cache_scope"
    private const val DATA_SAVER = "data_saver"

    @Volatile private var made: OkHttpClient? = null
    @Volatile private var standing: Pairing? = null
    private val ended = MutableStateFlow(0)

    /** Moves each time a pairing ends, is refused or is replaced; a player
     *  still holding that pairing's queue lets it go. */
    val forgotten: StateFlow<Int> get() = ended

    private fun pairing(context: Context): Pairing = standing ?: synchronized(this) {
        standing ?: context.applicationContext.let { app ->
            Pairing(
                prefs = prefs(app),
                vault = Vault,
                forget = {
                    MusicTree.forget()
                    Kept.drop(app)
                    // Audio bytes are personal too. A phone paired to somebody
                    // else must not be able to replay what the prior account
                    // happened to hear before it was paired again.
                    ListeningCache.clear(app)
                    ended.update { it + 1 }
                },
                complain = { message, why -> Log.e(TAG, message, why) },
            )
        }.also { standing = it }
    }

    /** @throws VaultUnavailable while the keystore does not answer. */
    fun token(context: Context): String? = pairing(context).token()

    fun paired(context: Context): Boolean = pairing(context).paired()

    fun refused(context: Context): Boolean = pairing(context).refused()

    private fun prefs(context: Context): SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun updateCheckedAt(context: Context): Long = prefs(context).getLong("update_checked_at", 0L)

    fun updateChecked(context: Context, at: Long) = prefs(context).edit { putLong("update_checked_at", at) }

    /** A non-secret namespace for cached audio. It changes with every pairing;
     * the bearer itself never becomes a filename or a cache database key. */
    fun cacheScope(context: Context): String =
        prefs(context).getString(CACHE_SCOPE, "unpaired") ?: "unpaired"

    /** An explicit phone setting. The normal car stream remains the original
     * library file; this only changes newly-built MusicTree stream addresses. */
    fun savesData(context: Context): Boolean = prefs(context).getBoolean(DATA_SAVER, false)

    fun setSavesData(context: Context, enabled: Boolean) {
        prefs(context).edit { putBoolean(DATA_SAVER, enabled) }
        MusicTree.forget()
    }

    fun client(context: Context): OkHttpClient = made ?: synchronized(this) {
        made ?: build(context.applicationContext).also { made = it }
    }

    private fun build(app: Context): OkHttpClient =
        OpusHttp.client(Opus.userAgent(app)) { token(app)?.let { "Authorization" to "Bearer $it" } }
            .newBuilder()
            .addNetworkInterceptor { chain ->
                val request = chain.request()
                chain.proceed(request).also { response ->
                    pairing(app).answered(request.url.encodedPath, request.header("Authorization") != null, response.code)
                }
            }
            .build()

    /** The person signs in once and that session is spent on minting the
     *  car's bearer; the password is never kept. */
    suspend fun pair(context: Context, username: String, password: String) = withContext(Dispatchers.IO) {
        val client = OpusHttp.client(Opus.userAgent(context)) { null }
        val json = "application/json; charset=utf-8".toMediaType()
        val login = Request.Builder()
            .url(Opus.url("/api/auth/login"))
            .post(JSONObject().put("username", username).put("password", password).toString().toRequestBody(json))
            .build()
        val cookie = client.newCall(login).execute().use { response ->
            if (response.code == 401) throw BadCredentials()
            if (!response.isSuccessful) throw IOException("HTTP ${response.code} from /api/auth/login")
            response.headers("Set-Cookie").firstOrNull { it.startsWith("opus_session=") }?.substringBefore(';')
                ?: throw IOException("/api/auth/login set no session")
        }
        val mint = Request.Builder()
            .url(Opus.url("/api/auth/car-token"))
            .header("Cookie", cookie)
            .post(ByteArray(0).toRequestBody(null))
            .build()
        val token = client.newCall(mint).execute().use { response ->
            if (!response.isSuccessful) throw IOException("HTTP ${response.code} from /api/auth/car-token")
            JSONObject(response.body.string()).getString("token")
        }
        pairing(context).pair(token)
        prefs(context).edit(commit = true) { putString(CACHE_SCOPE, UUID.randomUUID().toString()) }
    }

    fun ensurePaired(context: Context) {
        if (token(context) == null) throw NotPaired()
    }
}
