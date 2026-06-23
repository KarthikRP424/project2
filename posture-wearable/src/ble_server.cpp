/**
 * ble_server.cpp
 * NimBLE GATT Server implementation for PostureGuard.
 */

#include "ble_server.h"
#include <cstring>

// ── Global flag set by command characteristic callback ────────────────────────
volatile bool g_calibrate_requested = false;

// ─────────────────────────────────────────────────────────────────────────────
//  Command characteristic write callback
// ─────────────────────────────────────────────────────────────────────────────
class CmdCallbacks : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pChar) override {
        std::string val = pChar->getValue();
        if (val.empty()) return;

        uint8_t cmd = (uint8_t)val[0];
        Serial.printf("[BLE] Command received: 0x%02X\n", cmd);

        switch (cmd) {
            case 0x01:  // Calibrate
                g_calibrate_requested = true;
                Serial.println("[BLE] Calibration requested via BLE");
                break;

            case 0x02:  // Deep sleep
                Serial.println("[BLE] Deep sleep command — going to sleep in 1s");
                delay(1000);
                esp_deep_sleep_start();
                break;

            case 0x03:  // Buzz alert
                PostureBLEServer::buzzAlert();
                break;

            default:
                Serial.printf("[BLE] Unknown command: 0x%02X\n", cmd);
                break;
        }
    }
};

// ─────────────────────────────────────────────────────────────────────────────
//  Server connection callbacks
// ─────────────────────────────────────────────────────────────────────────────
class ServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* pServer) override {
        Serial.println("[BLE] Central connected!");
        digitalWrite(PIN_LED, HIGH);   // Solid LED = connected
    }

    void onDisconnect(NimBLEServer* pServer) override {
        Serial.println("[BLE] Central disconnected — restarting advertising");
        NimBLEDevice::startAdvertising();
        digitalWrite(PIN_LED, LOW);
    }
};

// ─────────────────────────────────────────────────────────────────────────────
//  PostureBLEServer methods
// ─────────────────────────────────────────────────────────────────────────────
void PostureBLEServer::begin(const char* deviceName) {
    // Initialize NimBLE stack
    NimBLEDevice::init(deviceName);
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);  // Max TX power

    // Create GATT server
    _pServer = NimBLEDevice::createServer();
    _pServer->setCallbacks(new ServerCallbacks());

    // Create service
    NimBLEService* pService = _pServer->createService(SVC_UUID);

    // Data characteristic (Notify, 12 bytes)
    _pDataChar = pService->createCharacteristic(
        DATA_UUID,
        NIMBLE_PROPERTY::NOTIFY
    );

    // Command characteristic (Write)
    _pCmdChar = pService->createCharacteristic(
        CMD_UUID,
        NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::WRITE_NR
    );
    _pCmdChar->setCallbacks(new CmdCallbacks());

    // Start service
    pService->start();

    // Advertising
    _pAdvertising = NimBLEDevice::getAdvertising();
    _pAdvertising->addServiceUUID(SVC_UUID);
    _pAdvertising->setScanResponse(true);
    _pAdvertising->setMinPreferred(0x06);

    NimBLEDevice::startAdvertising();

    Serial.printf("[BLE] Advertising as \"%s\"  MAC: %s\n",
                  deviceName,
                  NimBLEDevice::getAddress().toString().c_str());
}

void PostureBLEServer::sendOrientationData(float pitch, float roll, float battery) {
    if (!isConnected()) return;

    // Pack 3 floats as little-endian bytes
    uint8_t buf[12];
    memcpy(buf + 0, &pitch,   sizeof(float));
    memcpy(buf + 4, &roll,    sizeof(float));
    memcpy(buf + 8, &battery, sizeof(float));

    _pDataChar->setValue(buf, 12);
    _pDataChar->notify();
}

bool PostureBLEServer::isConnected() const {
    return _pServer && (_pServer->getConnectedCount() > 0);
}

void PostureBLEServer::buzzAlert() {
    // 880 Hz for 300 ms using LEDC PWM
    ledcSetup(0, 880, 8);
    ledcAttachPin(PIN_BUZZER, 0);
    ledcWrite(0, 128);        // 50% duty cycle
    delay(300);
    ledcWrite(0, 0);          // Off
    ledcDetachPin(PIN_BUZZER);
    Serial.println("[Buzzer] Alert buzzed!");
}

float PostureBLEServer::readBatteryPercent() {
    // ESP32 ADC1_CH6 (GPIO34) reads 0–4095 → map to 0–100%
    // Assumes 100k/100k voltage divider from 4.2V Li-Po to 3.3V ADC max
    int raw = analogRead(PIN_BATTERY);
    // Voltage at ADC pin: (raw / 4095.0) * 3.3V
    // Actual battery voltage: adcV * 2 (divider)
    float adcVoltage = (raw / 4095.0f) * 3.3f;
    float battVoltage = adcVoltage * 2.0f;

    // Li-Po: 3.0V (0%) → 4.2V (100%)
    float pct = ((battVoltage - 3.0f) / (4.2f - 3.0f)) * 100.0f;
    return constrain(pct, 0.0f, 100.0f);
}
