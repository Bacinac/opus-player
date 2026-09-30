package biz.boskovic.opus.core

import java.io.File
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertDoesNotThrow
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir

class UpdaterTest {
    private val digest = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    private val offer = Updater.Offer(412, digest)
    private val installed = Updater.Apk("biz.boskovic.opus.music", 400, setOf("opus-key"))
    private val good = Updater.Apk("biz.boskovic.opus.music", 412, setOf("opus-key"))

    private fun refusal(archive: Updater.Apk?): String =
        assertThrows<UpdateRejected> {
            Updater.verify(offer, "/api/app/music.json", digest, installed) { archive }
        }.message.orEmpty()

    @Test
    fun `a matching package is accepted`() {
        assertDoesNotThrow { Updater.verify(offer, "/api/app/music.json", digest, installed) { good } }
    }

    @Test
    fun `a digest that differs is refused before the package is opened`() {
        var opened = false
        assertThrows<UpdateRejected> {
            Updater.verify(offer, "/api/app/music.json", digest.replace('a', 'b'), installed) {
                opened = true
                good
            }
        }
        assertFalse(opened)
    }

    @Test
    fun `an unreadable package is refused`() {
        assertTrue(refusal(archive = null).contains("not a readable package"))
    }

    @Test
    fun `another app's package is refused`() {
        val other = Updater.Apk("biz.boskovic.opus.player", 412, setOf("opus-key"))
        assertTrue(refusal(archive = other).contains("is not biz.boskovic.opus.music"))
    }

    @Test
    fun `a version other than the one offered is refused`() {
        val older = Updater.Apk("biz.boskovic.opus.music", 411, setOf("opus-key"))
        assertTrue(refusal(archive = older).contains("version 411, not 412"))
    }

    @Test
    fun `a package signed by another key is refused`() {
        val forged = Updater.Apk("biz.boskovic.opus.music", 412, setOf("someone-else"))
        assertTrue(refusal(archive = forged).contains("not signed by this app's key"))
    }

    @Test
    fun `an unsigned package is refused even against an unsigned install`() {
        val unsigned = Updater.Apk("biz.boskovic.opus.music", 412, emptySet())
        assertThrows<UpdateRejected> {
            Updater.verify(offer, "/api/app/music.json", digest, Updater.Apk("biz.boskovic.opus.music", 400, emptySet())) { unsigned }
        }
    }

    @Test
    fun `a package that adds a signer is refused`() {
        val widened = Updater.Apk("biz.boskovic.opus.music", 412, setOf("opus-key", "someone-else"))
        assertTrue(refusal(archive = widened).contains("not signed by this app's key"))
    }

    @Test
    fun `the digest is lowercase hex of SHA-256`(@TempDir dir: File) {
        val file = File(dir, "update.apk").apply { writeText("abc") }
        assertEquals(digest, Updater.sha256(file))
    }
}
