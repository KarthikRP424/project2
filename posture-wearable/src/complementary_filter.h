/**
 * complementary_filter.h
 * Sensor fusion filter combining accelerometer (low-pass) and
 * gyroscope (high-pass) to produce stable pitch and roll angles.
 *
 * Equation:
 *   angle(t) = alpha * (angle(t-1) + gyro * dt) + (1 - alpha) * accel_angle
 *
 * alpha=0.98 → strongly trusts gyroscope short-term,
 *              corrects drift using accelerometer long-term.
 */

#pragma once
#include <Arduino.h>

struct IMUData {
    float ax, ay, az;   // m/s² (after calibration offsets)
    float gx, gy, gz;   // deg/s
};

struct Orientation {
    float pitch;   // degrees — forward/backward tilt
    float roll;    // degrees — side tilt
};

class ComplementaryFilter {
public:
    explicit ComplementaryFilter(float alpha = 0.98f);

    /**
     * Update filter with new IMU reading.
     * @param data     Raw (offset-corrected) IMU values.
     * @param dt_sec   Time delta since last call, in seconds.
     * @return         Fused orientation (pitch, roll) in degrees.
     */
    Orientation update(const IMUData& data, float dt_sec);

    /** Reset internal state (call after sensor re-init or calibration). */
    void reset();

    /** Return last computed orientation without new sensor data. */
    Orientation getOrientation() const { return _orientation; }

private:
    float       _alpha;
    Orientation _orientation;
    bool        _initialized;
};
