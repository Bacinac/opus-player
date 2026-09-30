package biz.boskovic.opus.player

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class OfferedTest {
    private val own = setOf("biz.boskovic.opus.player.updates", "biz.boskovic.opus.player.androidx-startup")
    private val gallery = "com.google.android.apps.photos.contentprovider"

    @Test
    fun `a photograph from another app's provider is taken`() {
        assertTrue(Offered.admits("content", gallery, "image/jpeg", own))
        assertTrue(Offered.admits("content", "media", "image/heic", own))
    }

    @Test
    fun `a video from another app's provider is taken`() {
        assertTrue(Offered.admits("content", "media", "video/mp4", own))
    }

    @Test
    fun `a file path is refused whatever it claims to be`() {
        assertFalse(Offered.admits("file", null, "image/jpeg", own))
        assertFalse(Offered.admits("file", "", "image/jpeg", own))
    }

    @Test
    fun `this app's own providers are refused`() {
        assertFalse(Offered.admits("content", "biz.boskovic.opus.player.updates", "image/jpeg", own))
        assertFalse(Offered.admits("content", "0@biz.boskovic.opus.player.updates", "image/jpeg", own))
        assertFalse(Offered.admits("content", "10@biz.boskovic.opus.player.androidx-startup", "video/mp4", own))
    }

    @Test
    fun `anything that is not a photograph or a video is refused`() {
        assertFalse(Offered.admits("content", gallery, "application/vnd.android.package-archive", own))
        assertFalse(Offered.admits("content", gallery, "text/plain", own))
        assertFalse(Offered.admits("content", gallery, "application/octet-stream", own))
    }

    @Test
    fun `a provider that will not say what it shared is refused`() {
        assertFalse(Offered.admits("content", gallery, null, own))
    }

    @Test
    fun `an address without a scheme or an authority is refused`() {
        assertFalse(Offered.admits(null, gallery, "image/jpeg", own))
        assertFalse(Offered.admits("content", null, "image/jpeg", own))
        assertFalse(Offered.admits("content", "", "image/jpeg", own))
        assertFalse(Offered.admits("https", "example.org", "image/jpeg", own))
    }
}
