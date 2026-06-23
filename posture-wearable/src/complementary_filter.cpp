/**
 * complementary_filter.cpp
 */

#include "complementary_filter.h"
#include <math.h>

ComplementaryFilter::ComplementaryFilter(float alpha)
    : _alpha(alpha), _initialized(false)
{
    _orientation = {0.0f, 0.0f};
}

Orientation ComplementaryFilter::update(const IMUData& data, float dt_sec) {
    // ── 1. Accelerometer-derived angles (stable long-term, noisy short-term) ──
    float accel_pitch = atan2f(data.ay, sqrtf(data.ax * data.ax + data.az * data.az))
                        * RAD_TO_DEG;
    float accel_roll  = atan2f(-data.ax, data.az) * RAD_TO_DEG;

    if (!_initialized) {
        // Seed the filter on first call
        _orientation.pitch = accel_pitch;
        _orientation.roll  = accel_roll;
        _initialized       = true;
        return _orientation;
    }

    // ── 2. Gyroscope integration (accurate short-term, drifts long-term) ──────
    float gyro_pitch = _orientation.pitch + data.gy * dt_sec;
    float gyro_roll  = _orientation.roll  + data.gx * dt_sec;

    // ── 3. Blend: alpha for gyro, (1-alpha) for accelerometer ────────────────
    _orientation.pitch = _alpha * gyro_pitch + (1.0f - _alpha) * accel_pitch;
    _orientation.roll  = _alpha * gyro_roll  + (1.0f - _alpha) * accel_roll;

    return _orientation;
}

void ComplementaryFilter::reset() {
    _orientation  = {0.0f, 0.0f};
    _initialized  = false;
}
