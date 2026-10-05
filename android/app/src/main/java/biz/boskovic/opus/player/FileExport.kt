package biz.boskovic.opus.player

import java.io.IOException
import java.io.OutputStream
import java.util.Base64
import java.util.UUID

internal class FileExport {
    data class Status(val state: String, val at: Long, val detail: String = "")

    private class Transfer(val id: String, val size: Long) {
        var state = "waiting"
        var at = 0L
        var detail = ""
        var output: OutputStream? = null
        var discard: (() -> Unit)? = null
    }

    @Volatile private var transfer: Transfer? = null

    fun currentId(): String? = transfer?.id

    @Synchronized
    fun begin(size: Long): String {
        require(size >= 0) { "a file size cannot be negative" }
        check(transfer?.state !in setOf("waiting", "ready")) { "another file is being saved" }
        return UUID.randomUUID().toString().also { transfer = Transfer(it, size) }
    }

    @Synchronized
    fun status(id: String): Status = transfer?.takeIf { it.id == id }?.let {
        Status(it.state, it.at, it.detail)
    } ?: Status("cancelled", 0)

    @Synchronized
    fun accept(id: String, output: OutputStream, discard: () -> Unit) {
        val active = transfer?.takeIf { it.id == id && it.state == "waiting" }
        if (active == null) {
            try { output.close() } finally { discard() }
            return
        }
        active.output = output
        active.discard = discard
        active.state = "ready"
    }

    @Synchronized
    fun write(id: String, at: Long, encoded: String): Long {
        val active = transfer?.takeIf { it.id == id && it.state == "ready" }
            ?: throw IOException("this file is no longer being saved")
        try {
            require(encoded.length <= ((PIECE + 2) / 3) * 4) { "the file piece is too large" }
            val bytes = Base64.getDecoder().decode(encoded)
            require(bytes.isNotEmpty() && bytes.size <= PIECE) { "the file piece is empty or too large" }
            require(at == active.at && bytes.size.toLong() <= active.size - at) { "the file piece is out of order or exceeds its size" }
            checkNotNull(active.output).write(bytes)
            active.at += bytes.size
            return active.at
        } catch (failure: Exception) {
            fail(id, failure.message ?: "the file could not be written")
            throw IOException(active.detail, failure)
        }
    }

    @Synchronized
    fun finish(id: String) {
        val active = transfer?.takeIf { it.id == id && it.state == "ready" }
            ?: throw IOException("this file is no longer being saved")
        try {
            check(active.at == active.size) { "the saved file is incomplete" }
            active.output?.close()
            active.output = null
            active.discard = null
            active.state = "done"
        } catch (failure: Exception) {
            fail(id, failure.message ?: "the file could not be closed")
            throw IOException(active.detail, failure)
        }
    }

    @Synchronized
    fun fail(id: String, detail: String) {
        transfer?.takeIf { it.id == id && it.state in setOf("waiting", "ready") }?.let {
            it.state = "failed"
            it.detail = detail
            clean(it)
        }
    }

    @Synchronized
    fun cancel(id: String? = transfer?.id) {
        transfer?.takeIf { it.id == id && it.state in setOf("waiting", "ready") }?.let {
            it.state = "cancelled"
            clean(it)
        }
    }

    private fun clean(active: Transfer) {
        val failures = mutableListOf<String>()
        try { active.output?.close() } catch (failure: Exception) {
            failures.add(failure.message ?: "the unfinished file could not be closed")
        }
        active.output = null
        try { active.discard?.invoke() } catch (failure: Exception) {
            failures.add(failure.message ?: "the unfinished file could not be removed")
        }
        active.discard = null
        if (failures.isNotEmpty()) {
            active.state = "failed"
            active.detail = (listOf(active.detail).filter(String::isNotEmpty) + failures).joinToString("; ")
        }
    }

    companion object {
        const val PIECE = 128 * 1024
    }
}
