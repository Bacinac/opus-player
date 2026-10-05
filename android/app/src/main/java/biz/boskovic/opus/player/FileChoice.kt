package biz.boskovic.opus.player

internal class FileChoice<T> {
    private var callback: ((T?) -> Unit)? = null
    private var busy = false

    fun begin(receive: (T?) -> Unit): Boolean {
        if (busy) {
            receive(null)
            return false
        }
        busy = true
        callback = receive
        return true
    }

    fun finish(value: T?) {
        busy = false
        val receive = callback
        callback = null
        receive?.invoke(value)
    }

    fun cancel() {
        val receive = callback
        callback = null
        receive?.invoke(null)
    }
}
