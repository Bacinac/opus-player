package biz.boskovic.opus.music

import android.content.SharedPreferences
import java.lang.reflect.Proxy
import java.security.GeneralSecurityException
import java.security.ProviderException
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class PairingTest {
    private val stored = HashMap<String, Any?>()
    private val vault = Keystore()
    private val shown = mutableListOf("artists", "Rijeka FM")
    private val queued = mutableListOf("track:1", "track:2")
    private val complaints = mutableListOf<String>()
    private val pauses = mutableListOf<Long>()

    private val pairing = Pairing(
        prefs = prefs(),
        vault = vault,
        forget = {
            shown.clear()
            queued.clear()
        },
        complain = { message, _ -> complaints += message },
        pause = { pauses += it },
    )

    private val busy get() = SealUnavailable(ProviderException("Keystore operation failed"))

    private class Keystore : Sealer {
        val failures = ArrayDeque<GeneralSecurityException>()
        var opened = 0

        override fun seal(plain: String): String {
            failures.removeFirstOrNull()?.let { throw it }
            return "sealed:$plain"
        }

        override fun open(sealed: String): String {
            opened++
            failures.removeFirstOrNull()?.let { throw it }
            return sealed.removePrefix("sealed:")
        }
    }

    private inline fun <reified T : Any> proxy(crossinline answer: (String, Array<Any?>) -> Any?): T =
        Proxy.newProxyInstance(T::class.java.classLoader, arrayOf(T::class.java)) { _, method, args ->
            answer(method.name, args ?: emptyArray())
        } as T

    private fun prefs(): SharedPreferences = proxy { name, args ->
        when (name) {
            "getString", "getBoolean", "getLong" -> stored[args[0]] ?: args[1]
            "contains" -> args[0] in stored
            "edit" -> editor()
            else -> throw UnsupportedOperationException(name)
        }
    }

    private fun editor(): SharedPreferences.Editor {
        val puts = HashMap<String, Any?>()
        val removes = HashSet<String>()
        lateinit var self: SharedPreferences.Editor
        self = proxy { name, args ->
            when (name) {
                "putString", "putBoolean", "putLong" -> self.also { puts[args[0] as String] = args[1] }
                "remove" -> self.also { removes += args[0] as String }
                "commit", "apply" -> {
                    removes.forEach(stored::remove)
                    stored.putAll(puts)
                    if (name == "commit") true else null
                }
                else -> throw UnsupportedOperationException(name)
            }
        }
        return self
    }

    private fun forgotten() = shown.isEmpty() && queued.isEmpty()

    @Test
    fun `a phone never paired has no token and forgets nothing`() {
        assertNull(pairing.token())
        assertFalse(pairing.paired())
        assertFalse(forgotten())
    }

    @Test
    fun `a sealed token is opened once and kept open`() {
        stored["sealed_token"] = "sealed:bearer"
        assertEquals("bearer", pairing.token())
        assertEquals("bearer", pairing.token())
        assertEquals(1, vault.opened)
    }

    @Test
    fun `a plain token from before the vault is sealed and the plain copy removed`() {
        stored["token"] = "bearer"
        assertEquals("bearer", pairing.token())
        assertEquals("sealed:bearer", stored["sealed_token"])
        assertFalse("token" in stored)
        assertFalse(forgotten())
    }

    @Test
    fun `a plain token stays usable, and unsealed, while the keystore does not answer`() {
        stored["token"] = "bearer"
        repeat(3) { vault.failures += busy }
        assertEquals("bearer", pairing.token())
        assertEquals("bearer", stored["token"])
        assertFalse("sealed_token" in stored)
        assertEquals(1, complaints.size)
        assertFalse(forgotten())
    }

    @Test
    fun `a keystore that fails for a moment is asked again`() {
        stored["sealed_token"] = "sealed:bearer"
        vault.failures += busy
        assertEquals("bearer", pairing.token())
        assertEquals(listOf(100L), pauses)
    }

    @Test
    fun `a keystore that keeps failing keeps the car paired and says why`() {
        stored["sealed_token"] = "sealed:bearer"
        repeat(3) { vault.failures += busy }
        val said = assertThrows<VaultUnavailable> { pairing.token() }
        assertTrue(said.cause is SealUnavailable)
        assertEquals("sealed:bearer", stored["sealed_token"])
        assertTrue(pairing.paired())
        assertFalse(forgotten())

        assertEquals("bearer", pairing.token())
    }

    @Test
    fun `a token that can never be opened again is deleted and everything shown under it forgotten`() {
        stored["sealed_token"] = "sealed:bearer"
        vault.failures += SealBroken("the key that sealed the token is gone")
        assertNull(pairing.token())
        assertFalse(pairing.paired())
        assertTrue(forgotten())
        assertEquals(1, complaints.size)
    }

    @Test
    fun `a refusal forgets what was shown and queued, once`() {
        pairing.answered("/api/library/music", carried = true, code = 401)
        assertTrue(pairing.refused())
        assertTrue(forgotten())

        queued += "track:3"
        pairing.answered("/api/library/search", carried = true, code = 401)
        assertEquals(listOf("track:3"), queued)
    }

    @Test
    fun `a 403 is a refusal as well`() {
        pairing.answered("/api/play/track/1/stream", carried = true, code = 403)
        assertTrue(pairing.refused())
        assertTrue(forgotten())
    }

    @Test
    fun `a request taken again lifts the refusal`() {
        pairing.answered("/api/library/music", carried = true, code = 401)
        pairing.answered("/api/library/music", carried = true, code = 200)
        assertFalse(pairing.refused())
    }

    @Test
    fun `an open route answering does not lift a refusal`() {
        pairing.answered("/api/library/music", carried = true, code = 401)
        pairing.answered("/api/art", carried = true, code = 200)
        pairing.answered("/api/ping", carried = true, code = 200)
        pairing.answered("/api/app/music.json", carried = true, code = 200)
        assertTrue(pairing.refused())
    }

    @Test
    fun `only a request that carried the bearer behind the door says anything`() {
        pairing.answered("/api/app/music.json", carried = true, code = 401)
        pairing.answered("/api/auth/car-token", carried = true, code = 403)
        pairing.answered("/api/art", carried = true, code = 403)
        pairing.answered("/api/library/music", carried = false, code = 401)
        pairing.answered("/api/library/music", carried = true, code = 500)
        pairing.answered("/api/library/artist/9", carried = true, code = 404)
        assertFalse(pairing.refused())
        assertFalse(forgotten())
    }

    @Test
    fun `pairing again seals the new token, lifts a refusal and forgets the old pairing`() {
        stored["sealed_token"] = "sealed:old"
        assertEquals("old", pairing.token())
        pairing.answered("/api/library/music", carried = true, code = 401)
        shown += "artists"
        queued += "track:9"

        pairing.pair("new")

        assertEquals("sealed:new", stored["sealed_token"])
        assertFalse(pairing.refused())
        assertTrue(forgotten())
        assertEquals("new", pairing.token())
    }

    @Test
    fun `a pairing the keystore cannot seal keeps nothing of itself`() {
        stored["sealed_token"] = "sealed:old"
        repeat(3) { vault.failures += busy }
        assertThrows<VaultUnavailable> { pairing.pair("new") }
        assertEquals("sealed:old", stored["sealed_token"])
        assertFalse(forgotten())
        assertEquals("old", pairing.token())
    }

    @Test
    fun `a seal broken for good fails the pairing the same way`() {
        vault.failures += SealBroken("the sealed token can never be opened again")
        assertThrows<VaultUnavailable> { pairing.pair("new") }
        assertFalse(pairing.paired())
    }
}
