package com.pichy.ai.local

import android.content.Context
import com.arm.aichat.AiChat
import com.arm.aichat.InferenceEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.filter
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

class LocalLlamaBridge(context: Context) {
    interface Callback {
        fun onReady()
        fun onComplete(text: String)
        fun onError(message: String)
    }

    private val engine = AiChat.getInferenceEngine(context.applicationContext)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    @Volatile
    var ready: Boolean = false
        private set

    fun load(modelPath: String, systemPrompt: String, callback: Callback) {
        scope.launch {
            try {
                withTimeout(60_000L) {
                    engine.state.filter {
                        it is InferenceEngine.State.Initialized ||
                            it is InferenceEngine.State.ModelReady ||
                            it is InferenceEngine.State.Error
                    }.first()
                }

                val state = engine.state.value
                if (state is InferenceEngine.State.Error) {
                    throw state.exception
                }
                if (state is InferenceEngine.State.ModelReady) {
                    engine.cleanUp()
                }

                engine.loadModel(modelPath)
                engine.setSystemPrompt(systemPrompt)
                ready = true
                withContext(Dispatchers.Main) { callback.onReady() }
            } catch (t: Throwable) {
                ready = false
                withContext(Dispatchers.Main) {
                    callback.onError(t.message ?: t.javaClass.simpleName)
                }
            }
        }
    }

    fun generate(message: String, maxTokens: Int, callback: Callback) {
        if (!ready) {
            callback.onError("Local brain is not ready")
            return
        }

        scope.launch {
            try {
                val out = StringBuilder()
                engine.sendUserPrompt(message, maxTokens).collect { token ->
                    out.append(token)
                }
                withContext(Dispatchers.Main) {
                    callback.onComplete(out.toString().trim())
                }
            } catch (t: Throwable) {
                withContext(Dispatchers.Main) {
                    callback.onError(t.message ?: t.javaClass.simpleName)
                }
            }
        }
    }

    fun close() {
        ready = false
        try {
            engine.destroy()
        } catch (_: Throwable) {
        }
        scope.cancel()
    }
}
