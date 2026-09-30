package biz.boskovic.opus.music

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class ControllersTest {
    private val hosts = listOf(
        "com.google.android.projection.gearhead",
        "com.google.android.googlequicksearchbox",
        "com.android.bluetooth",
    )

    @Test
    fun `Android Auto, the assistant and bluetooth are let in by the name the platform matched to them`() {
        for (host in hosts) assertTrue(Controllers.admits(host, verified = true, trusted = false), host)
    }

    @Test
    fun `a host's name that the platform could not match to the caller is only a claim, and refused`() {
        for (host in hosts) assertFalse(Controllers.admits(host, verified = false, trusted = false), host)
    }

    @Test
    fun `a controller the platform trusts is let in whatever it says it is called`() {
        assertTrue(Controllers.admits("com.android.systemui", verified = true, trusted = true))
        assertTrue(Controllers.admits("android.media.session.MediaController", verified = false, trusted = true))
    }

    @Test
    fun `any other app is refused under its own true name`() {
        assertFalse(Controllers.admits("com.example.player", verified = true, trusted = false))
        assertFalse(Controllers.admits("biz.boskovic.opus.music", verified = true, trusted = false))
        assertFalse(Controllers.admits("android.media.session.MediaController", verified = false, trusted = false))
        assertFalse(Controllers.admits("", verified = false, trusted = false))
    }

    @Test
    fun `a name that only resembles a host is refused`() {
        assertFalse(Controllers.admits("com.google.android.projection.gearhead.evil", verified = true, trusted = false))
        assertFalse(Controllers.admits("evil.com.google.android.projection.gearhead", verified = true, trusted = false))
        assertFalse(Controllers.admits("COM.GOOGLE.ANDROID.PROJECTION.GEARHEAD", verified = true, trusted = false))
    }
}
