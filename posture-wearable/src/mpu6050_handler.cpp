/**
 * mpu6050_handler.cpp
 */

#include "mpu6050_handler.h"
#include <Wire.h>

// Gravity constant (m/s²)
static const float GRAVITY = 9.80665f;
// Number of calibration samples
static const int CALIB_SAMPLES = 200;

bool MPU6050Handler::begin() {
    // SDA=21, SCL=22 (ESP32 defaults)
    Wire.begin(21, 22);

    if (!_mpu.begin()) {
        Serial.println("[MPU6050] Sensor not found on I2C!");
        _available = false;
        return false;
    }

    // Configure ranges
    _mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    _mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    _mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

    _available = true;
    Serial.println("[MPU6050] Initialized OK (±8G, ±500°/s)");
    return true;
}

IMUData MPU6050Handler::readCalibrated() {
    sensors_event_t a, g, temp;
    _mpu.getEvent(&a, &g, &temp);

    IMUData d;
    // Acceleration in m/s², corrected by offsets
    d.ax = a.acceleration.x - _off_ax;
    d.ay = a.acceleration.y - _off_ay;
    d.az = a.acceleration.z - _off_az;

    // Gyroscope in deg/s (Adafruit returns rad/s → convert)
    d.gx = (g.gyro.x - _off_gx) * RAD_TO_DEG;
    d.gy = (g.gyro.y - _off_gy) * RAD_TO_DEG;
    d.gz = (g.gyro.z - _off_gz) * RAD_TO_DEG;

    return d;
}

void MPU6050Handler::calibrateOffsets() {
    Serial.println("[MPU6050] Calibrating offsets — keep sensor STILL!");

    double sum_ax = 0, sum_ay = 0, sum_az = 0;
    double sum_gx = 0, sum_gy = 0, sum_gz = 0;

    sensors_event_t a, g, temp;

    for (int i = 0; i < CALIB_SAMPLES; i++) {
        _mpu.getEvent(&a, &g, &temp);

        sum_ax += a.acceleration.x;
        sum_ay += a.acceleration.y;
        sum_az += a.acceleration.z;
        sum_gx += g.gyro.x;
        sum_gy += g.gyro.y;
        sum_gz += g.gyro.z;

        delay(10);  // 10ms per sample → ~2s total
    }

    _off_ax = (float)(sum_ax / CALIB_SAMPLES);
    _off_ay = (float)(sum_ay / CALIB_SAMPLES);
    // Keep Z offset ≈ gravity removed
    _off_az = (float)(sum_az / CALIB_SAMPLES) - GRAVITY;

    _off_gx = (float)(sum_gx / CALIB_SAMPLES);
    _off_gy = (float)(sum_gy / CALIB_SAMPLES);
    _off_gz = (float)(sum_gz / CALIB_SAMPLES);

    Serial.printf("[MPU6050] Offsets: ax=%.3f ay=%.3f az=%.3f gx=%.3f gy=%.3f gz=%.3f\n",
                  _off_ax, _off_ay, _off_az, _off_gx, _off_gy, _off_gz);
}
