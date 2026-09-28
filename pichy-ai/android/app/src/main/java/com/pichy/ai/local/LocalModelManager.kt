package com.pichy.ai.local

import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class LocalModelManager(context: Context) {
    interface DownloadCallback {
        fun onProgress(downloaded: Long, total: Long)
        fun onComplete(path: String)
        fun onError(message: String)
    }

    companion object {
        const val MODEL_NAME = "Qwen3-1.7B Q4_K_M"
        const val MODEL_SIZE: Long = 1_282_439_264L
        const val MODEL_SHA256 = "d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5"
        const val MODEL_URL =
            "https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q4_K_M.gguf?download=true"
        const val MODEL_FILE = "Qwen3-1.7B-Q4_K_M.gguf"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val modelDir = File(context.applicationContext.filesDir, "models")
    val modelFile = File(modelDir, MODEL_FILE)

    fun isInstalled(): Boolean = modelFile.isFile && modelFile.length() == MODEL_SIZE

    fun download(callback: DownloadCallback) {
        scope.launch {
            try {
                modelDir.mkdirs()
                val part = File(modelDir, MODEL_FILE + ".part")
                var existing = if (part.isFile) part.length() else 0L
                var connection = openConnection(existing)

                if (existing > 0L && connection.responseCode != HttpURLConnection.HTTP_PARTIAL) {
                    connection.disconnect()
                    part.delete()
                    existing = 0L
                    connection = openConnection(0L)
                }

                if (connection.responseCode !in 200..299) {
                    throw IllegalStateException("Hugging Face HTTP " + connection.responseCode)
                }

                val append = existing > 0L && connection.responseCode == HttpURLConnection.HTTP_PARTIAL
                var downloaded = if (append) existing else 0L
                var nextProgress = downloaded

                connection.inputStream.use { input ->
                    FileOutputStream(part, append).buffered().use { output ->
                        val buffer = ByteArray(1024 * 1024)
                        while (true) {
                            val n = input.read(buffer)
                            if (n <= 0) break
                            output.write(buffer, 0, n)
                            downloaded += n
                            if (downloaded >= nextProgress) {
                                val current = downloaded
                                withContext(Dispatchers.Main) {
                                    callback.onProgress(current, MODEL_SIZE)
                                }
                                nextProgress = downloaded + 8L * 1024L * 1024L
                            }
                        }
                    }
                }
                connection.disconnect()

                if (part.length() != MODEL_SIZE) {
                    throw IllegalStateException(
                        "Model size mismatch: " + part.length() + " / " + MODEL_SIZE
                    )
                }

                val digest = sha256(part)
                if (!digest.equals(MODEL_SHA256, ignoreCase = true)) {
                    part.delete()
                    throw IllegalStateException("Model SHA-256 verification failed")
                }

                if (modelFile.exists()) modelFile.delete()
                if (!part.renameTo(modelFile)) {
                    throw IllegalStateException("Could not finalize local model")
                }

                withContext(Dispatchers.Main) {
                    callback.onComplete(modelFile.absolutePath)
                }
            } catch (t: Throwable) {
                withContext(Dispatchers.Main) {
                    callback.onError(t.message ?: t.javaClass.simpleName)
                }
            }
        }
    }

    private fun openConnection(existing: Long): HttpURLConnection {
        val connection = URL(MODEL_URL).openConnection() as HttpURLConnection
        connection.instanceFollowRedirects = true
        connection.connectTimeout = 30_000
        connection.readTimeout = 60_000
        connection.setRequestProperty("Accept-Encoding", "identity")
        if (existing > 0L) {
            connection.setRequestProperty("Range", "bytes=" + existing + "-")
        }
        connection.connect()
        return connection
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val n = input.read(buffer)
                if (n <= 0) break
                digest.update(buffer, 0, n)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    fun close() {
        scope.cancel()
    }
}
