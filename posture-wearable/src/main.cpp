/**
 * main.cpp  —  PostureGuard ESP32 Wearable Firmware
 *
 * Loop runs at ~100Hz (10ms per iteration).
 * Every 50ms: if BLE connected, sends pitch/roll/battery packet.
 * Responds to BLE commands: calibrate, sleep, buzz.
 *
 * Pin map:
 *   GPIO 2   — Built-in LED (heartbeat / status)
 *   GPIO 21  — I2C SDA → MPU6050
 *   GPIO 22  — I2C SCL → MPU6050
 *   GPIO 25  — Buzzer (via NPN transistor)
 *   GPIO 34  — Battery ADC (voltage divider)
 */

#include <Arduino.h>
#include "mpu6050_handler.h"
#include "complementary_filter.h"
#include "ble_server.h"

// ── Objects ───────────────────────────────────────────────────────────────────
MPU6050Handler    imu;
ComplementaryFilter filter(0.98f);
PostureBLEServer  bleServer;

// ── Timing ────────────────────────────────────────────────────────────────────
static unsigned long lastLoopMs    = 0;
static unsigned long lastSendMs    = 0;
static unsigned long lastHeartMs   = 0;
static bool          ledState      = false;

// ── Constants ─────────────────────────────────────────────────────────────────
static const unsigned long LOOP_INTERVAL_MS = 10;    // 100 Hz main loop
static const unsigned long SEND_INTERVAL_MS = 50;    // 20 Hz BLE notify
static const unsigned long HEART_INTERVAL_MS = 1000; // 1 Hz LED heartbeat

// ─────────────────────────────────────────────────────────────────────────────
//  Helpers
// ─────────────────────────────────────────────────────────────────────────────
void blinkError(int count) {
    /**
     * Blink LED 'count' times rapidly — indicates error code at startup.
     * e.g., blinkError(3) = MPU6050 not found
     */
    for (int i = 0; i < count; i++) {
        digitalWrite(PIN_LED, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  delay(120);
    }
    delay(600);
}

void runCalibration() {
    Serial.println("[Main] Running calibration (2s — keep still!)");
    // Flash LED rapidly during calibration
    for (int i = 0; i < 20; i++) {
        digitalWrite(PIN_LED, i % 2 == 0); delay(100);
    }
    imu.calibrateOffsets();
    filter.reset();
    Serial.println("[Main] Calibration done!");
    // 3 quick blinks = success
    blinkError(3);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Setup
// ─────────────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(500);
    Serial.println("\n\n=== PostureGuard ESP32 Wearable v1.0 ===");

    // Pin setup
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
    pinMode(PIN_BUZZER, OUTPUT);
    digitalWrite(PIN_BUZZER, LOW);

    // ── MPU6050 init (retry 5 times) ──────────────────────────────────────
    bool mpuOk = false;
    for (int attempt = 1; attempt <= 5; attempt++) {
        Serial.printf("[Main] MPU6050 init attempt %d/5…\n", attempt);
        if (imu.begin()) {
            mpuOk = true;
            break;
        }
        blinkError(attempt);  // Error blink code = attempt number
        delay(500);
    }

    if (!mpuOk) {
        Serial.println("[FATAL] MPU6050 not found after 5 attempts. Halting.");
        while (true) {
            blinkError(5);
            delay(1000);
        }
    }

    // ── Initial calibration ───────────────────────────────────────────────
    Serial.println("[Main] Starting initial calibration…");
    runCalibration();

    // ── BLE server ────────────────────────────────────────────────────────
    bleServer.begin("PostureGuard-ESP32");

    // ── ADC for battery ───────────────────────────────────────────────────
    analogSetAttenuation(ADC_11db);  // Allow full 3.3V range on ADC

    lastLoopMs = millis();
    Serial.println("[Main] Ready. Waiting for BLE connection…");
}

// ─────────────────────────────────────────────────────────────────────────────
//  Loop
// ─────────────────────────────────────────────────────────────────────────────
void loop() {
    unsigned long now = millis();

    // Enforce 100 Hz rate
    if (now - lastLoopMs < LOOP_INTERVAL_MS) return;
    float dt = (now - lastLoopMs) / 1000.0f;
    lastLoopMs = now;

    // ── 1. Read sensor ────────────────────────────────────────────────────
    if (!imu.isAvailable()) return;
    IMUData data = imu.readCalibrated();

    // ── 2. Run complementary filter ───────────────────────────────────────
    Orientation orientation = filter.update(data, dt);

    // ── 3. Handle BLE calibration command ─────────────────────────────────
    if (g_calibrate_requested) {
        g_calibrate_requested = false;
        runCalibration();
    }

    // ── 4. Send BLE notification every 50ms ───────────────────────────────
    if (now - lastSendMs >= SEND_INTERVAL_MS) {
        lastSendMs = now;
        float battery = PostureBLEServer::readBatteryPercent();
        bleServer.sendOrientationData(orientation.pitch, orientation.roll, battery);

        // Debug output to serial monitor
        Serial.printf("Pitch: %6.2f°  Roll: %6.2f°  Bat: %4.1f%%  BLE: %s\n",
                      orientation.pitch, orientation.roll, battery,
                      bleServer.isConnected() ? "Connected" : "Advertising");
    }

    // ── 5. LED heartbeat ──────────────────────────────────────────────────
    if (now - lastHeartMs >= HEART_INTERVAL_MS) {
        lastHeartMs = now;
        if (!bleServer.isConnected()) {
            // Slow blink when advertising
            ledState = !ledState;
            digitalWrite(PIN_LED, ledState);
        }
        // If connected, LED stays HIGH (set in BLE callback)
    }
}
