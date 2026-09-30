package biz.boskovic.opus.music

import android.content.SharedPreferences
import androidx.core.content.edit

/** The car's standing with the Player: the bearer minted at pairing, kept
 *  sealed, and whether the Player last refused it. The bearer dies with the
 *  person's password, so a refusal is kept until a request is taken again.
 *
 *  Everything this phone showed or queued under a pairing is forgotten when
 *  that pairing ends, is refused, or is replaced. */
internal class Pairing(
    private val prefs: SharedPreferences,
    private val vault: Sealer,
    private val forget: () -> Unit,
    private val complain: (String, Throwable) -> Unit,
    private val pause: (Long) -> Unit = Thread::sleep,
) {
    @Volatile private var opened: String? = null

    /** @throws VaultUnavailable while the keystore does not answer; the token
     *  is kept for the next try. */
    fun token(): String? = opened ?: synchronized(this) {
        opened ?: unseal()?.also { opened = it }
    }

    fun paired(): Boolean = prefs.contains(SEALED) || prefs.contains(PLAIN)

    fun refused(): Boolean = prefs.getBoolean(REFUSED, false)

    /** What the Player said to a request; only a request that carried the
     *  bearer to a route behind the door says anything about it. The open
     *  routes are the Player's OPEN_PATHS and OPEN_PREFIXES. */
    fun answered(path: String, carried: Boolean, code: Int) {
        if (!carried || path in OPEN || OPEN_UNDER.any(path::startsWith)) return
        synchronized(this) {
            when {
                (code == 401 || code == 403) && !refused() -> {
                    prefs.edit(commit = true) { putBoolean(REFUSED, true) }
                    forget()
                }
                code in 200..299 && refused() -> prefs.edit(commit = true) { putBoolean(REFUSED, false) }
            }
        }
    }

    /** @throws VaultUnavailable when the token could not be sealed; nothing
     *  of the new pairing is kept then. */
    fun pair(token: String) {
        val sealed = try {
            trying { vault.seal(token) }
        } catch (broken: SealBroken) {
            throw VaultUnavailable(broken)
        }
        synchronized(this) {
            prefs.edit(commit = true) {
                putString(SEALED, sealed)
                remove(PLAIN)
                putBoolean(REFUSED, false)
            }
            opened = token
        }
        forget()
    }

    private fun unseal(): String? {
        prefs.getString(PLAIN, null)?.let { plain ->
            migrate(plain)
            return plain
        }
        val sealed = prefs.getString(SEALED, null) ?: return null
        return try {
            trying { vault.open(sealed) }
        } catch (broken: SealBroken) {
            complain("the car token can never be opened again; the phone has to be paired again", broken)
            prefs.edit(commit = true) { remove(SEALED) }
            forget()
            null
        }
    }

    private fun migrate(plain: String) {
        val sealed = try {
            trying { vault.seal(plain) }
        } catch (later: VaultUnavailable) {
            complain("the car token stays unsealed until the keystore answers", later)
            return
        } catch (later: SealBroken) {
            complain("the car token stays unsealed until the keystore answers", later)
            return
        }
        prefs.edit(commit = true) {
            putString(SEALED, sealed)
            remove(PLAIN)
        }
    }

    private fun <T> trying(work: () -> T): T {
        var last: SealUnavailable? = null
        for (wait in PAUSES) {
            try {
                return work()
            } catch (busy: SealUnavailable) {
                last = busy
                if (wait > 0) pause(wait)
            }
        }
        throw VaultUnavailable(checkNotNull(last))
    }

    private companion object {
        const val SEALED = "sealed_token"
        const val PLAIN = "token"
        const val REFUSED = "refused"
        val PAUSES = longArrayOf(100, 400, 0)
        val OPEN = setOf("/api/ping", "/api/art")
        val OPEN_UNDER = listOf("/api/auth/", "/api/app/")
    }
}
