# Smart Bluetooth-Based AI Posture Correction System 🧘‍♂️💻

A next-generation, cross-platform, privacy-focused IoT and Computer Vision system designed to monitor sitting posture in real time. It uses local MediaPipe Pose processing to analyze posture via a laptop webcam, or streams orientation metrics from a custom ESP32 BLE wearable or an Android companion app. It alerts users via audio warnings and haptic vibrations when slouching is detected, promoting habit-forming posture correction.

---

## 📂 Project Architecture & Directory Structure

The project is structured into three main component repositories:

```
project2/
├── README.md                      # This main project manual
├── posture-laptop/                # PyQt6 Desktop Hub (Python)
│   ├── config/                    # SQLite database storage & settings
│   ├── core/                      # MediaPipe CV, BLE client, WebSocket server
│   ├── ui/                        # PyQt6 styled dashboard and tabs
│   ├── workers/                   # Camera & sensor multi-threading workers
│   ├── main.py                    # Desktop application entry point
│   └── requirements.txt           # Python library dependencies
│
├── posture-wearable/              # ESP32 IoT Wearable Firmware (PlatformIO/C++)
│   ├── src/                       # IMU complementary filter, NimBLE server
│   ├── platformio.ini             # Build environments and library config
│   └── README_WEARABLE.md         # Pinout diagrams & flash guide
│
└── posture-android/               # Kotlin Android Companion App (Jetpack Compose)
    ├── app/                       # Source code, service, view models, composables
    ├── build.gradle               # Gradle build configurations
    └── settings.gradle            # Project settings
```

---

## ⚙️ Installation & Running instructions

### 💻 1. PyQt6 Desktop Application (Laptop Hub)

The desktop app acts as the central coordinator, hosting the local database, UI graphs, webcam Pose processing, and communication servers.

#### Prerequisites
- Python 3.9 - 3.11 (tested on standard environments)
- Integrated or USB webcam

#### Setup
1. Navigate to the desktop project folder:
   ```bash
   cd posture-laptop
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python main.py
   ```

---

### 📱 2. Android Companion Application (Phone Sensor)

The Android companion application reads internal accelerometer/gyroscope sensors to track posture and receives vibration commands from the laptop.

#### Prerequisites
- Android Studio (Jellyfish or newer)
- Android SDK 26 (Android 8.0) or higher

#### Setup
1. Open the `posture-android` folder in Android Studio.
2. Allow Gradle sync to complete and fetch dependencies (Jetpack Compose, OkHttp, Serialization, Lifecycle).
3. Connect an Android device with Developer Mode enabled.
4. Run the `:app` configuration to deploy the app to your phone.

---

### 🔌 3. ESP32 Wearable Firmware (DIY Sensor)

The ESP32 firmware reads raw linear acceleration and angular velocity from the MPU6050, filters the raw data using a complementary filter, and streams pitch and roll values over BLE.

#### Prerequisites
- VS Code with PlatformIO extension installed
- ESP32 Development Board + MPU6050 sensor

#### Hardware Pin Connections
- **MPU6050 SDA** ──► **ESP32 GPIO 21**
- **MPU6050 SCL** ──► **ESP32 GPIO 22**
- **MPU6050 VCC** ──► **ESP32 3.3V**
- **MPU6050 GND** ──► **ESP32 GND**
- **Buzzer Positive** ──► **ESP32 GPIO 25** (with NPN transistor amplifier)
- **Status LED** ──► **ESP32 GPIO 2** (Onboard LED)

#### Flashing the Firmware
1. Open the `posture-wearable` folder in VS Code with PlatformIO.
2. PlatformIO will automatically configure libraries (`Adafruit MPU6050`, `NimBLE-Arduino`).
3. Connect the ESP32 to your computer via USB.
4. Run the upload command:
   ```bash
   pio run --target upload
   ```

---

## 📡 Communication Protocols

### BLE (ESP32 Wearable to Laptop)
- **GATT Service UUID:** `4fafc201-1fb5-459e-8fcc-c5c9c331914b`
- **GATT Notification Characteristic (Data Stream):** `beb5483e-36e1-4688-b7f5-ea07361b26a8`
  - Sends a continuous 12-byte payload: `[Float Pitch (4B)][Float Roll (4B)][Float Battery (4B)]`
- **GATT Write Characteristic (Control Commands):** `cba1d00f-8c3b-4c3d-b4f2-9e8a5b28a2a5`
  - Write `0x01` ──► Triggers MPU6050 Recalibration
  - Write `0x02` ──► Puts ESP32 into Deep Sleep
  - Write `0x03` ──► Sounds the Wearable Buzzer for 300ms

### WebSockets (Android Companion to Laptop)
- **Server:** Python WebSocket server running inside the PyQt6 app (Port `8765`).
- **Device Stream:** Phone streams JSON coordinates: `{"pitch": float, "roll": float}`.
- **Laptop Command:** Laptop triggers vibration commands on target posture breach: `{"command": "vibrate", "pattern": [0, 200, 100, 200]}`.
