package biz.boskovic.opus.player

import android.content.Intent
import android.os.Bundle
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import org.json.JSONObject

/** Speech into the page's keyboard, heard by the recognizer the box already
 *  has — on the Shield Google's, the one its own search listens with. What is
 *  heard goes to the page while it is being said, so the words fill the box
 *  as they are spoken; the last reading is the one searched for. */
class Hearing(private val host: PlayerActivity, private val tell: (JSONObject) -> Unit) {

    private var recognizer: SpeechRecognizer? = null

    /** A keyboard is on the page, so the remote's microphone key means it. */
    @Volatile var wanted = false

    fun possible(): Boolean = SpeechRecognizer.isRecognitionAvailable(host)

    fun listen(language: String) {
        val ear = recognizer ?: SpeechRecognizer.createSpeechRecognizer(host).also {
            it.setRecognitionListener(listener)
            recognizer = it
        }
        ear.cancel()
        ear.startListening(Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_WEB_SEARCH)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
            putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
        })
    }

    fun stop() {
        recognizer?.cancel()
    }

    fun refused() {
        failed(SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS)
    }

    fun release() {
        recognizer?.destroy()
        recognizer = null
    }

    private fun heard(results: Bundle?, done: Boolean) {
        val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull().orEmpty()
        tell(JSONObject().put("text", text).put("done", done))
    }

    private fun failed(error: Int) {
        Log.e(TAG, "speech recognition failed with error $error")
        tell(JSONObject().put("error", error))
    }

    private val listener = object : RecognitionListener {
        override fun onPartialResults(partialResults: Bundle?) = heard(partialResults, false)
        override fun onResults(results: Bundle?) = heard(results, true)

        override fun onError(error: Int) {
            // silence, or nothing it could make words of: nobody spoke, which
            // is an answer and not a fault
            if (error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT || error == SpeechRecognizer.ERROR_NO_MATCH) {
                tell(JSONObject().put("unheard", true))
            } else {
                failed(error)
            }
        }

        override fun onReadyForSpeech(params: Bundle?) = Unit
        override fun onBeginningOfSpeech() = Unit
        override fun onRmsChanged(rmsdB: Float) = Unit
        override fun onBufferReceived(buffer: ByteArray?) = Unit
        override fun onEndOfSpeech() = Unit
        override fun onEvent(eventType: Int, params: Bundle?) = Unit
    }

    private companion object {
        const val TAG = "OpusHearing"
    }
}
