package biz.boskovic.opus.player

import biz.boskovic.opus.core.Opus
import java.security.MessageDigest
import java.security.SecureRandom

/** The key the bridge answers to, and the only place it is handed out: a
 *  document-start script that the WebView runs in OPUS frames alone and that
 *  gives it to the top one. */
internal object Bridge {
    const val NAME = "opusTvBridge"

    fun origins(): Set<String> = setOf(Opus.site)

    class Key(private val secret: String = fresh()) {
        fun opens(given: String): Boolean = MessageDigest.isEqual(secret.toByteArray(), given.toByteArray())

        fun script(): String = """
            (() => {
              const bridge = window.$NAME;
              if (window !== window.top || !bridge) return;
              const key = '$secret';
              window.opusTv = new Proxy({}, {
                get: (_, name) => typeof bridge[name] === 'function' ? (...args) => bridge[name](key, ...args) : undefined
              });
            })();
        """.trimIndent()
    }

    private fun fresh(): String =
        ByteArray(32).also(SecureRandom()::nextBytes).joinToString("") { "%02x".format(it) }
}
