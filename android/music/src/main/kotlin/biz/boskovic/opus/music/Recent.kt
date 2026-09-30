package biz.boskovic.opus.music

/** A map that holds at most [capacity] entries, each for [lifetimeMs]. */
internal class Recent<K : Any, V : Any>(
    private val capacity: Int,
    private val lifetimeMs: Long,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    private class Entry<V>(val value: V, val at: Long)

    private val entries = object : LinkedHashMap<K, Entry<V>>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<K, Entry<V>>): Boolean = size > capacity
    }

    @Synchronized
    operator fun get(key: K): V? {
        val entry = entries[key] ?: return null
        if (clock() - entry.at >= lifetimeMs) {
            entries.remove(key)
            return null
        }
        return entry.value
    }

    @Synchronized
    operator fun set(key: K, value: V) {
        entries[key] = Entry(value, clock())
    }

    @Synchronized
    fun clear() = entries.clear()
}
