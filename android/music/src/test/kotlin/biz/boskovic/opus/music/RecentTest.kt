package biz.boskovic.opus.music

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test

class RecentTest {
    private var now = 0L
    private val recent = Recent<String, Int>(capacity = 3, lifetimeMs = 1_000) { now }

    @Test
    fun `an entry is kept for its lifetime and no longer`() {
        recent["a"] = 1
        now = 999
        assertEquals(1, recent["a"])
        now = 1_000
        assertNull(recent["a"])
    }

    @Test
    fun `the least recently used entry leaves first`() {
        recent["a"] = 1
        recent["b"] = 2
        recent["c"] = 3
        assertEquals(1, recent["a"])
        recent["d"] = 4
        assertNull(recent["b"])
        assertEquals(1, recent["a"])
        assertEquals(3, recent["c"])
        assertEquals(4, recent["d"])
    }

    @Test
    fun `setting an entry again starts its lifetime again`() {
        recent["a"] = 1
        now = 900
        recent["a"] = 2
        now = 1_500
        assertEquals(2, recent["a"])
    }

    @Test
    fun `clearing forgets everything`() {
        recent["a"] = 1
        recent["b"] = 2
        recent.clear()
        assertNull(recent["a"])
        assertNull(recent["b"])
    }
}
