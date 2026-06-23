/**
 * mpu6050_handler.h
 * Wrapper around Adafruit MPU6050 library.
 * Reads raw accel + gyro, applies stored calibration offsets.
 */

#pragma once
#include <Arduino.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include "complementary_filter.h"  // for IMUData struct

class MPU6050Handler {
public:
    MPU6050Handler() = default;

    /**
     * Initialize I2C and MPU6050. Returns true on success.
     * Sets accel range ±8G, gyro range ±500 dps.
     */
    bool begin();

    /**
     * Read sensor, apply offsets, return calibrated IMUData.
     * ax/ay/az in m/s², gx/gy/gz in deg/s.
     */
    IMUData readCalibrated();

    /**
     * Collect 200 samples at rest, store average as zero offsets.
     * Call while sensor is stationary on a flat surface.
     * ~2 seconds of sampling.
     */
    void calibrateOffsets();

    bool isAvailable() const { return _available; }

private:
    Adafruit_MPU6050 _mpu;
    bool    _available = false;

    // Calibration offsets (subtracted from every reading)
    float _off_ax = 0, _off_ay = 0, _off_az = 0;
    float _off_gx = 0, _off_gy = 0, _off_gz = 0;
};
