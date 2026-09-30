package biz.boskovic.opus.player

import android.view.KeyEvent

/** OK on the remote or a tap on the screen: the only thing another app is ever
 *  opened in answer to. One press opens one thing, and only just after it. */
internal class Gesture(private val clock: () -> Long, private val window: Long = WINDOW_MS) {
    private var at: Long? = null

    @Synchronized
    fun felt() {
        at = clock()
    }

    @Synchronized
    fun spend(): Boolean {
        val felt = at ?: return false
        at = null
        return clock() - felt in 0..window
    }

    fun leaves(mainFrame: Boolean): Boolean = mainFrame && spend()

    companion object {
        const val WINDOW_MS = 1_500L

        private val ACTIVATING = setOf(
            KeyEvent.KEYCODE_DPAD_CENTER,
            KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_NUMPAD_ENTER,
            KeyEvent.KEYCODE_BUTTON_A,
            KeyEvent.KEYCODE_BUTTON_SELECT,
            KeyEvent.KEYCODE_SPACE,
        )

        fun activates(keyCode: Int): Boolean = keyCode in ACTIVATING
    }
}
