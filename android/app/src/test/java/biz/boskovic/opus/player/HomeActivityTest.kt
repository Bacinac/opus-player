package biz.boskovic.opus.player

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class HomeActivityTest {
    @Test
    fun `home offers the six applications chosen for the television`() {
        assertEquals(
            listOf(
                "biz.boskovic.opus.player",
                "com.uniqcast.uniqtv.eronet",
                "hr.a1.android.tv.xploretv",
                "com.netflix.ninja",
                "com.aspiro.tidal",
                "com.spotify.tv.android",
            ),
            HomeOrder.PRIMARY,
        )
    }
}
