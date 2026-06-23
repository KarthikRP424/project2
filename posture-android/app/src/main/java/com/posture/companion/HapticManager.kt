package com.posture.companion

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log

/**
 * HapticManager — centralised vibration utility.
 *
 * All patterns follow the VibrationEffect convention:
 *   [wait_before_start_ms, on_ms, off_ms, on_ms, …]
 *
 * Requires android.permission.VIBRATE in the manifest.
 */
object HapticManager {

    private const val TAG = "HapticManager"

    // ─── Pre-defined patterns ────────────────────────────────────────────────

    /** Single short buzz — e.g. a minor posture alert */
    val SHORT_ALERT: LongArray = longArrayOf(0, 150)

    /** Single long buzz — e.g. severe posture alert */
    val LONG_ALERT: LongArray = longArrayOf(0, 600)

    /** Pulse pattern — soft rhythmic feedback */
    val PULSE_PATTERN: LongArray = longArrayOf(0, 100, 150, 100, 150, 100)

    /** Triple buzz — e.g. critical alert / connection event */
    val TRIPLE_BUZZ: LongArray = longArrayOf(0, 200, 100, 200, 100, 200)

    // ─── Public API ──────────────────────────────────────────────────────────

    /**
     * Vibrate with the given [pattern].
     * Uses [VibrationEffect] on API 26+. The pattern is played once (repeat = -1).
     */
    fun vibrate(context: Context, pattern: LongArray) {
        try {
            val vibrator = getVibrator(context) ?: run {
                Log.w(TAG, "No vibrator available on this device")
                return
            }

            if (!vibrator.hasVibrator()) {
                Log.w(TAG, "Device does not support vibration")
                return
            }

            val effect = VibrationEffect.createWaveform(pattern, -1 /* no repeat */)
            vibrator.vibrate(effect)
            Log.d(TAG, "Vibrating with pattern: ${pattern.toList()}")

        } catch (e: Exception) {
            Log.e(TAG, "Vibration failed", e)
        }
    }

    /**
     * Cancel any ongoing vibration.
     */
    fun cancel(context: Context) {
        try {
            getVibrator(context)?.cancel()
        } catch (e: Exception) {
            Log.e(TAG, "Cancel vibration failed", e)
        }
    }

    /**
     * Vibrate using a named pre-defined pattern key sent by the server.
     * Valid keys: "short", "long", "pulse", "triple"
     */
    fun vibratePreset(context: Context, preset: String) {
        val pattern = when (preset.lowercase()) {
            "short"  -> SHORT_ALERT
            "long"   -> LONG_ALERT
            "pulse"  -> PULSE_PATTERN
            "triple" -> TRIPLE_BUZZ
            else     -> {
                Log.w(TAG, "Unknown preset: $preset, defaulting to SHORT_ALERT")
                SHORT_ALERT
            }
        }
        vibrate(context, pattern)
    }

    // ─── Private helpers ──────────────────────────────────────────────────────

    private fun getVibrator(context: Context): Vibrator? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
            vm?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }
}
