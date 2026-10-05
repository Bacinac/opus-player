package biz.boskovic.opus.player

import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.OutputStream
import java.util.Base64
import org.junit.jupiter.api.Assertions.assertArrayEquals
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class FileExportTest {
    private fun encoded(bytes: ByteArray) = Base64.getEncoder().encodeToString(bytes)

    @Test
    fun `bounded pieces produce the complete original and completed files are retained`() {
        val saved = FileExport()
        val original = ByteArray(FileExport.PIECE * 2 + 17) { (it % 251).toByte() }
        val id = saved.begin(original.size.toLong())
        val output = ByteArrayOutputStream()
        var removed = false
        saved.accept(id, output) { removed = true }
        for (at in original.indices step FileExport.PIECE) {
            val end = minOf(at + FileExport.PIECE, original.size)
            assertEquals(end.toLong(), saved.write(id, at.toLong(), encoded(original.copyOfRange(at, end))))
        }
        saved.finish(id)
        saved.cancel(id)
        assertEquals("done", saved.status(id).state)
        assertArrayEquals(original, output.toByteArray())
        assertFalse(removed)
    }

    @Test
    fun `incomplete files are removed instead of reported as saved`() {
        val saved = FileExport()
        val id = saved.begin(4)
        var removed = false
        saved.accept(id, ByteArrayOutputStream()) { removed = true }
        saved.write(id, 0, encoded(byteArrayOf(1, 2)))
        assertThrows(IOException::class.java) { saved.finish(id) }
        assertEquals("failed", saved.status(id).state)
        assertTrue(removed)
    }

    @Test
    fun `out of order oversized and malformed pieces remove their unfinished files`() {
        for ((at, bytes) in listOf(1L to encoded(byteArrayOf(1)),
            0L to encoded(ByteArray(FileExport.PIECE + 1)), 0L to "not base64")) {
            val saved = FileExport()
            val id = saved.begin(FileExport.PIECE.toLong() * 2)
            var removed = false
            saved.accept(id, ByteArrayOutputStream()) { removed = true }
            assertThrows(IOException::class.java) { saved.write(id, at, bytes) }
            assertEquals("failed", saved.status(id).state)
            assertTrue(removed)
        }
    }

    @Test
    fun `late picker results and writes cannot consume a replacement transfer`() {
        val saved = FileExport()
        val old = saved.begin(1)
        saved.cancel(old)
        val current = saved.begin(1)
        var discarded = false
        saved.accept(old, ByteArrayOutputStream()) { discarded = true }
        assertTrue(discarded)
        assertThrows(IOException::class.java) { saved.write(old, 0, encoded(byteArrayOf(1))) }
        saved.cancel(old)
        assertEquals("waiting", saved.status(current).state)
    }

    @Test
    fun `provider write failure closes and removes the partial file`() {
        val saved = FileExport()
        val id = saved.begin(1)
        var closed = false
        var removed = false
        saved.accept(id, object : OutputStream() {
            override fun write(byte: Int) { throw IOException("provider unavailable") }
            override fun close() { closed = true }
        }) { removed = true }
        assertThrows(IOException::class.java) { saved.write(id, 0, encoded(byteArrayOf(1))) }
        assertEquals("provider unavailable", saved.status(id).detail)
        assertTrue(closed && removed)
    }

    @Test
    fun `cancellation cleanup failure remains visible`() {
        val saved = FileExport()
        val id = saved.begin(1)
        saved.accept(id, ByteArrayOutputStream()) { throw IOException("provider refused deletion") }
        saved.cancel(id)
        assertEquals("failed", saved.status(id).state)
        assertEquals("provider refused deletion", saved.status(id).detail)
    }

    @Test
    fun `only one provider request is active and empty files complete normally`() {
        val saved = FileExport()
        val id = saved.begin(0)
        assertThrows(IllegalStateException::class.java) { saved.begin(0) }
        saved.accept(id, ByteArrayOutputStream()) {}
        saved.finish(id)
        assertEquals("done", saved.status(id).state)
        assertTrue(saved.begin(0) != id)
    }
}
