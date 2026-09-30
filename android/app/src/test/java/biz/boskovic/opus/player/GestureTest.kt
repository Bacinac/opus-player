package biz.boskovic.opus.player

import android.view.KeyEvent
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class GestureTest {
    private var now = 10_000L
    private val gesture = Gesture({ now })

    @Test
    fun `nothing is opened before anybody pressed anything`() {
        assertFalse(gesture.spend())
        assertFalse(gesture.leaves(mainFrame = true))
    }

    @Test
    fun `a press opens one thing and only one`() {
        gesture.felt()
        now += 200
        assertTrue(gesture.spend())
        assertFalse(gesture.spend())
    }

    @Test
    fun `a press is good only for a moment`() {
        gesture.felt()
        now += Gesture.WINDOW_MS
        assertTrue(gesture.spend())

        gesture.felt()
        now += Gesture.WINDOW_MS + 1
        assertFalse(gesture.spend())
    }

    @Test
    fun `a clock that runs backwards opens nothing`() {
        gesture.felt()
        now -= 1
        assertFalse(gesture.spend())
    }

    @Test
    fun `a frame inside the page never leaves, and does not use up the press`() {
        gesture.felt()
        assertFalse(gesture.leaves(mainFrame = false))
        assertTrue(gesture.leaves(mainFrame = true))
        assertFalse(gesture.leaves(mainFrame = true))
    }

    @Test
    fun `OK, enter and a gamepad's A are presses`() {
        for (key in intArrayOf(
            KeyEvent.KEYCODE_DPAD_CENTER,
            KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_NUMPAD_ENTER,
            KeyEvent.KEYCODE_BUTTON_A,
            KeyEvent.KEYCODE_BUTTON_SELECT,
            KeyEvent.KEYCODE_SPACE,
        )) {
            assertTrue(Gesture.activates(key), "key $key")
        }
    }

    @Test
    fun `moving the focus, going back and the media keys are not`() {
        for (key in intArrayOf(
            KeyEvent.KEYCODE_DPAD_UP,
            KeyEvent.KEYCODE_DPAD_DOWN,
            KeyEvent.KEYCODE_DPAD_LEFT,
            KeyEvent.KEYCODE_DPAD_RIGHT,
            KeyEvent.KEYCODE_BACK,
            KeyEvent.KEYCODE_HOME,
            KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE,
            KeyEvent.KEYCODE_MEDIA_NEXT,
            KeyEvent.KEYCODE_VOLUME_UP,
        )) {
            assertFalse(Gesture.activates(key), "key $key")
        }
    }
}
