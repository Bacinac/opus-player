package biz.boskovic.opus.player

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class FileChoiceTest {
    @Test
    fun `single and multiple selections complete exactly once`() {
        for (files in listOf(listOf("one"), listOf("one", "two"))) {
            val picker = FileChoice<List<String>>()
            val replies = mutableListOf<List<String>?>()
            assertTrue(picker.begin { replies.add(it) })
            picker.finish(files)
            picker.finish(null)
            assertEquals(listOf(files), replies)
        }
    }

    @Test
    fun `a second picker cannot consume the first result`() {
        val picker = FileChoice<List<String>>()
        val first = mutableListOf<List<String>?>()
        val second = mutableListOf<List<String>?>()
        assertTrue(picker.begin { first.add(it) })
        assertFalse(picker.begin { second.add(it) })
        picker.finish(listOf("first"))
        assertEquals(listOf(listOf("first")), first)
        assertEquals(listOf<List<String>?>(null), second)
    }

    @Test
    fun `destroyed or navigated pages reject a late result and unblock after it returns`() {
        val picker = FileChoice<List<String>>()
        val replies = mutableListOf<List<String>?>()
        assertTrue(picker.begin { replies.add(it) })
        picker.cancel()
        picker.cancel()
        picker.finish(listOf("late"))
        assertEquals(listOf<List<String>?>(null), replies)
        assertTrue(picker.begin { replies.add(it) })
        picker.finish(null)
        assertEquals(listOf<List<String>?>(null, null), replies)
    }
}
