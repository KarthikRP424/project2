package com.posture.companion

import android.app.*
import android.content.Context
import android.content.Intent
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.os.*
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.Serializable
import kotlin.math.*

private const val CHANNEL_ID   = "posture_monitor"
private const val NOTIF_ID     = 1001
private const val SEND_RATE_MS = 100L   // 10 Hz sensor stream

@Serializable
data class SensorPacket(val pitch: Float, val roll: Float, val timestamp: Long)

@Serializable
data class CommandPacket(val command: String, val pattern: List<Long> = emptyList())

/**
 * Foreground service that:
 * 1. Reads accelerometer + gyroscope at GAME rate.
 * 2. Applies Complementary Filter to compute pitch and roll.
 * 3. Streams JSON packets to the laptop over WebSocket every 100ms.
 * 4. Handles incoming vibration commands from the laptop.
 */
class SensorService : Service(), SensorEventListener {

    // ── Binder for IPC with MainActivity ────────────────────────────────────
    inner class LocalBinder : Binder() {
        fun getService(): SensorService = this@SensorService
    }
    private val binder = LocalBinder()

    // ── Sensor ───────────────────────────────────────────────────────────────
    private lateinit var sensorManager: SensorManager
    private var accelSensor: Sensor? = null
    private var gyroSensor: Sensor? = null

    // Raw values
    private val accel = FloatArray(3)
    private val gyro  = FloatArray(3)

    // Complementary filter state
    private var pitchAngle = 0f
    private var rollAngle  = 0f
    private var lastTimestampNs = 0L
    private val alpha = 0.98f

    // ── Networking ────────────────────────────────────────────────────────────
    private var webSocketClient: WebSocketClient? = null
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var streamJob: Job? = null

    // ── Haptic ────────────────────────────────────────────────────────────────
    private lateinit var hapticManager: HapticManager

    // ─────────────────────────────────────────────────────────────────────────

    override fun onCreate() {
        super.onCreate()
        sensorManager = getSystemService(SENSOR_SERVICE) as SensorManager
        accelSensor   = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
        gyroSensor    = sensorManager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
        hapticManager = HapticManager(this)

        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildNotification()
        startForeground(NOTIF_ID, notification)
        return START_STICKY
    }

    override fun onBind(intent: Intent): IBinder = binder

    override fun onDestroy() {
        stopStreaming()
        serviceScope.cancel()
        super.onDestroy()
    }

    // ── Public API (called via binder) ────────────────────────────────────────

    fun startStreaming(ip: String, port: Int = 8765) {
        registerSensors()

        val url = "ws://$ip:$port"
        webSocketClient = WebSocketClient(
            onMessage  = ::handleIncomingCommand,
            onConnected    = { android.util.Log.i("SensorService", "WS connected to $url") },
            onDisconnected = { android.util.Log.w("SensorService", "WS disconnected") }
        )
        webSocketClient?.connect(url)

        // Launch periodic sender coroutine
        streamJob = serviceScope.launch {
            while (isActive) {
                val packet = SensorPacket(pitchAngle, rollAngle, System.currentTimeMillis())
                webSocketClient?.sendMessage(Json.encodeToString(packet))
                delay(SEND_RATE_MS)
            }
        }
    }

    fun stopStreaming() {
        streamJob?.cancel()
        webSocketClient?.disconnect()
        sensorManager.unregisterListener(this)
    }

    fun getCurrentAngles(): Pair<Float, Float> = Pair(pitchAngle, rollAngle)

    // ── Sensor callbacks ──────────────────────────────────────────────────────

    override fun onSensorChanged(event: SensorEvent) {
        when (event.sensor.type) {
            Sensor.TYPE_ACCELEROMETER -> {
                accel[0] = event.values[0]
                accel[1] = event.values[1]
                accel[2] = event.values[2]
            }
            Sensor.TYPE_GYROSCOPE -> {
                gyro[0] = event.values[0]   // rad/s
                gyro[1] = event.values[1]
                gyro[2] = event.values[2]

                // Complementary filter update
                val nowNs = event.timestamp
                if (lastTimestampNs != 0L) {
                    val dt = (nowNs - lastTimestampNs) / 1_000_000_000f  // seconds

                    // Accel-derived angles (degrees)
                    val accelPitch = Math.toDegrees(
                        atan2(accel[1].toDouble(),
                              sqrt(accel[0] * accel[0] + accel[2] * accel[2]).toDouble())
                    ).toFloat()
                    val accelRoll = Math.toDegrees(
                        atan2((-accel[0]).toDouble(), accel[2].toDouble())
                    ).toFloat()

                    // Gyro integration (rad/s → deg) + blend
                    pitchAngle = alpha * (pitchAngle + Math.toDegrees(gyro[1].toDouble()).toFloat() * dt) +
                                 (1f - alpha) * accelPitch
                    rollAngle  = alpha * (rollAngle  + Math.toDegrees(gyro[0].toDouble()).toFloat() * dt) +
                                 (1f - alpha) * accelRoll
                }
                lastTimestampNs = nowNs
            }
        }
    }

    override fun onAccuracyChanged(sensor: Sensor, accuracy: Int) { /* not used */ }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private fun registerSensors() {
        accelSensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
        gyroSensor?.let {
            sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME)
        }
    }

    private fun handleIncomingCommand(json: String) {
        try {
            val cmd = Json.decodeFromString<CommandPacket>(json)
            if (cmd.command == "vibrate") {
                val pattern = if (cmd.pattern.isNotEmpty()) cmd.pattern.toLongArray()
                              else longArrayOf(0, 300, 100, 300)
                hapticManager.vibrate(pattern)
            }
        } catch (e: Exception) {
            android.util.Log.w("SensorService", "Bad command JSON: $e")
        }
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID, "PostureGuard Monitor",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Real-time posture sensor streaming"
        }
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PostureGuard Active")
            .setContentText("Streaming sensor data to your laptop")
            .setSmallIcon(android.R.drawable.ic_menu_compass)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }
}
