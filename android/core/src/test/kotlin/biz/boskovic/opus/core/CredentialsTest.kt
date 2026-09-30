package biz.boskovic.opus.core

import java.lang.reflect.Proxy
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class CredentialsTest {
    private val bearer = Credentials("OPUS-test/v0") { "Authorization" to "Bearer secret" }

    private fun Interceptor.forward(request: Request): Request {
        var sent: Request? = null
        val chain = Proxy.newProxyInstance(
            Interceptor.Chain::class.java.classLoader,
            arrayOf(Interceptor.Chain::class.java),
        ) { _, method, args ->
            when (method.name) {
                "request" -> request
                "proceed" -> (args[0] as Request).let { next ->
                    sent = next
                    Response.Builder().request(next).protocol(Protocol.HTTP_1_1).code(200).message("OK").build()
                }
                else -> throw UnsupportedOperationException(method.name)
            }
        } as Interceptor.Chain
        intercept(chain)
        return sent!!
    }

    private fun carrying(url: String) = Request.Builder()
        .url(url)
        .header("Authorization", "Bearer carried")
        .header("Cookie", "opus_session=carried")
        .build()

    private fun assertBare(sent: Request) {
        assertNull(sent.header("Authorization"))
        assertNull(sent.header("Cookie"))
    }

    @Test
    fun `the OPUS origin over https gets the credential and the agent`() {
        val sent = bearer.forward(Request.Builder().url(Opus.url("/api/library/music")).build())
        assertEquals("Bearer secret", sent.header("Authorization"))
        assertEquals("OPUS-test/v0", sent.header("User-Agent"))
    }

    @Test
    fun `a hop to another host loses every credential it carried`() {
        assertBare(bearer.forward(carrying("https://cdn.example.org/cover.jpg")))
    }

    @Test
    fun `the OPUS host over plain http is another origin`() {
        assertBare(bearer.forward(carrying("http://${Opus.origin.host}/api/library/music")))
    }

    @Test
    fun `another port on the OPUS host is another origin`() {
        assertBare(bearer.forward(carrying("https://${Opus.origin.host}:8443/api/library/music")))
    }

    @Test
    fun `a host that merely begins with the OPUS host is another origin`() {
        assertBare(bearer.forward(carrying("https://${Opus.origin.host}.example.org/api/library/music")))
    }

    @Test
    fun `without a credential none is sent`() {
        val sent = Credentials("OPUS-test/v0") { null }.forward(Request.Builder().url(Opus.url("/api/app/music.json")).build())
        assertNull(sent.header("Authorization"))
        assertNull(sent.header("Cookie"))
    }

    @Test
    fun `the client judges every hop, redirects included`() {
        val client = OpusHttp.client("OPUS-test/v0") { "Cookie" to "opus_session=x" }
        assertTrue(client.networkInterceptors.single() is Credentials)
        assertTrue(client.interceptors.none { it is Credentials })
        assertTrue(client.followRedirects)
    }

    @Test
    fun `a redirect to another host arrives there without the credential`() {
        MockWebServer().use { opus ->
            MockWebServer().use { elsewhere ->
                opus.start()
                elsewhere.start()
                opus.enqueue(MockResponse.Builder().code(302).setHeader("Location", elsewhere.url("/station.mp3")).build())
                elsewhere.enqueue(MockResponse.Builder().body("sound").build())
                val client = OkHttpClient.Builder()
                    .addNetworkInterceptor(Credentials("OPUS-test/v0", { it.port == opus.port }) { "Cookie" to "opus_device=box" })
                    .build()
                val asked = Request.Builder()
                    .url(opus.url("/api/radio/stream"))
                    .header("Authorization", "Bearer carried")
                    .header("Cookie", "opus_device=carried")
                    .build()

                client.newCall(asked).execute().use { assertEquals("sound", it.body.string()) }

                assertEquals("opus_device=box", opus.takeRequest().headers["Cookie"])
                val hop = elsewhere.takeRequest().headers
                assertNull(hop["Cookie"])
                assertNull(hop["Authorization"])
                assertNotEquals("OPUS-test/v0", hop["User-Agent"])
            }
        }
    }
}
