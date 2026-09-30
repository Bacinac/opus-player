package biz.boskovic.opus.player

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class AppMarksTest {
    @Test
    fun every_launcher_door_has_a_mark() {
        val marks = java.io.File("src/main/assets/apps").list()!!.map { it.removeSuffix(".png") }.toSet()
        assertEquals(HomeOrder.PRIMARY.toSet() + AppMarks.CAMERAS, marks)
    }
}
