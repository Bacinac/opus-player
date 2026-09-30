package biz.boskovic.opus.player

import biz.boskovic.opus.core.Opus
import org.graalvm.polyglot.Context
import org.graalvm.polyglot.Engine
import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.TestInstance

@TestInstance(TestInstance.Lifecycle.PER_CLASS)
class BridgeTest {
    private val secret = "0123456789abcdef".repeat(4)
    private val key = Bridge.Key(secret)
    private val js = Engine.newBuilder("js").option("engine.WarnInterpreterOnly", "false").build()

    @AfterAll
    fun close() = js.close()

    private fun <T> frame(top: Boolean, bridged: Boolean = true, then: (Context) -> T): T =
        Context.newBuilder("js").engine(js).build().use { context ->
            context.eval(
                "js",
                """
                var reached = [];
                var window = {};
                window.top = ${if (top) "window" else "{}"};
                ${if (bridged) "window.${Bridge.NAME} = { launch: function () { reached.push(Array.prototype.slice.call(arguments)); return true; } };" else ""}
                """.trimIndent(),
            )
            context.eval("js", key.script())
            then(context)
        }

    @Test
    fun `the top OPUS frame gets a bridge that hands every call the key first`() {
        frame(top = true) { page ->
            assertTrue(page.eval("js", "window.opusTv.launch('com.aspiro.tidal', '')").asBoolean())
            assertEquals("""[["$secret","com.aspiro.tidal",""]]""", page.eval("js", "JSON.stringify(reached)").asString())
        }
    }

    @Test
    fun `a frame inside the page gets no bridge`() {
        frame(top = false) { child ->
            assertEquals("undefined", child.eval("js", "typeof window.opusTv").asString())
            assertEquals("[]", child.eval("js", "JSON.stringify(reached)").asString())
        }
    }

    @Test
    fun `a page without the injected object gets no bridge`() {
        frame(top = true, bridged = false) { page ->
            assertEquals("undefined", page.eval("js", "typeof window.opusTv").asString())
        }
    }

    @Test
    fun `a name the box does not answer is not a function`() {
        frame(top = true) { page ->
            assertEquals("undefined", page.eval("js", "typeof window.opusTv.format").asString())
        }
    }

    @Test
    fun `the key opens only itself`() {
        assertTrue(key.opens(secret))
        assertFalse(key.opens(""))
        assertFalse(key.opens(secret.dropLast(1)))
        assertFalse(key.opens(secret + "0"))
        assertFalse(key.opens(secret.reversed()))
        assertFalse(key.opens(secret.uppercase()))
    }

    @Test
    fun `every bridge has a fresh key of its own`() {
        val said = Regex("const key = '([^']*)'")
        val one = said.find(Bridge.Key().script())!!.groupValues[1]
        val other = said.find(Bridge.Key().script())!!.groupValues[1]
        assertTrue(Regex("[0-9a-f]{64}").matches(one))
        assertNotEquals(one, other)
        assertFalse(Bridge.Key(one).opens(other))
    }

    @Test
    fun `the script is run in the OPUS origin alone, over https, whole`() {
        val rules = Bridge.origins()
        assertEquals(setOf(Opus.site), rules)
        val rule = rules.single()
        assertTrue(rule.startsWith("https://"))
        assertFalse(rule.contains('*'))
        assertFalse(rule.removePrefix("https://").contains('/'))
        assertTrue(Opus.ours("$rule/api/library/music"))
    }
}
