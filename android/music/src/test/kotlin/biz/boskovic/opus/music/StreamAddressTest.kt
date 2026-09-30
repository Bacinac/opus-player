package biz.boskovic.opus.music

import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class StreamAddressTest {
    @Test
    fun `prefetch can use the exact address playback uses for every codec`() {
        assertTrue(MusicTree.stream(42, "opus").endsWith("/api/play/track/42/stream?fmt=.opus"))
        assertTrue(MusicTree.stream(42, "").endsWith("/api/play/track/42/stream?fmt=.flac"))
    }

    @Test
    fun `data saver asks explicitly for compact opus`() {
        assertTrue(MusicTree.stream(42, "flac", compact = true)
            .endsWith("/api/play/track/42/stream?fmt=.opus&compact=1"))
    }
}
