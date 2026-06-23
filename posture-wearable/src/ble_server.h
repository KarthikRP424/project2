/**
 * ble_server.h
 * NimBLE GATT Server for PostureGuard ESP32 wearable.
 *
 * Service:         4fafc201-1fb5-459e-8fcc-c5c9c331914b
 * Data Char:       beb5483e-36e1-4688-b7f5-ea07361b26a8  (Notify)
 *   Packet layout: [float pitch][float roll][float battery] — 12 bytes LE
 * Command Char:    cba1d00f-8c3b-4c3d-b4f2-9e8a5b28a2a5  (Write)
 *   0x01 = Calibrate, 0x02 = Deep Sleep, 0x03 = Buzz
 */

#pragma once
#include <Arduino.h>
#include <NimBLEDevice.h>

// Pin assignments
#define PIN_LED     2
#define PIN_BUZZER  25
#define PIN_BATTERY 34   // ADC1_CH6 — connect to voltage divider

// Service & characteristic UUIDs
#define SVC_UUID  "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define DATA_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define CMD_UUID  "cba1d00f-8c3b-4c3d-b4f2-9e8a5b28a2a5"

extern volatile bool g_calibrate_requested;

class PostureBLEServer {
public:
    PostureBLEServer() = default;

    /**
     * Initialize NimBLE stack, create GATT server, service, and characteristics.
     * @param deviceName  BLE advertising name (max 29 chars).
     */
    void begin(const char* deviceName);

    /**
     * Pack pitch, roll, battery into 12-byte little-endian float array and notify.
     * @param pitch    degrees, forward/backward.
     * @param roll     degrees, left/right.
     * @param battery  percentage 0–100.
     */
    void sendOrientationData(float pitch, float roll, float battery);

    /** Return true if a central device is currently connected. */
    bool isConnected() const;

    /** Trigger onboard buzzer (blocking, 300 ms). */
    static void buzzAlert();

    /** Read battery ADC and scale to 0–100 %. */
    static float readBatteryPercent();

private:
    NimBLEServer*         _pServer       = nullptr;
    NimBLECharacteristic* _pDataChar     = nullptr;
    NimBLECharacteristic* _pCmdChar      = nullptr;
    NimBLEAdvertising*    _pAdvertising  = nullptr;
};
