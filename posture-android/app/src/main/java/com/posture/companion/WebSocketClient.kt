package com.posture.companion

import android.util.Log
import kotlinx.coroutines.*
import okhttp3.*

private const val TAG = "WebSocketClient"

/**
 * OkHttp WebSocket client wrapper with auto-reconnect using exponential backoff.
 *
 * @param onMessage      Called on every incoming text frame.
 * @param onConnected    Called when connection is established.
 * @param onDisconnected Called when disconnected (before reconnect attempt).
 */
class WebSocketClient(
    private val onMessage: (String) -> Unit,
    private val onConnected: () -> Unit = {},
    private val onDisconnected: () -> Unit = {}
) {
    private val client = OkHttpClient()
    private var webSocket: WebSocket? = null
    private var targetUrl: String = ""
    private var reconnectJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var reconnectDelaySec = 1L
    private var active = false

    fun connect(url: String) {
        targetUrl = url
        active = true
        reconnectDelaySec = 1L
        openSocket()
    }

    fun disconnect() {
        active = false
        reconnectJob?.cancel()
        webSocket?.close(1000, "User stopped streaming")
        webSocket = null
        Log.i(TAG, "Disconnected from $targetUrl")
    }

    fun sendMessage(json: String) {
        webSocket?.send(json) ?: Log.d(TAG, "Not connected — dropped message")
    }

    val isConnected: Boolean get() = webSocket != null

    // ── Internal ──────────────────────────────────────────────────────────────

    private fun openSocket() {
        if (!active) return
        Log.i(TAG, "Connecting to $targetUrl…")
        val request = Request.Builder().url(targetUrl).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(ws: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket connected!")
                reconnectDelaySec = 1L
                webSocket = ws
                onConnected()
            }

            override fun onMessage(ws: WebSocket, text: String) {
                onMessage(text)
            }

            override fun onClosed(ws: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WebSocket closed ($code): $reason")
                webSocket = null
                onDisconnected()
                scheduleReconnect()
            }

            override fun onFailure(ws: WebSocket, t: Throwable, response: Response?) {
                Log.w(TAG, "WebSocket failure: ${t.message}")
                webSocket = null
                onDisconnected()
                scheduleReconnect()
            }
        })
    }

    private fun scheduleReconnect() {
        if (!active) return
        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            Log.i(TAG, "Reconnecting in ${reconnectDelaySec}s…")
            delay(reconnectDelaySec * 1000)
            reconnectDelaySec = minOf(reconnectDelaySec * 2, 30L)  // Exponential backoff, max 30s
            openSocket()
        }
    }
}
