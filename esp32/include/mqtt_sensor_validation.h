#pragma once

#include <cmath>

inline bool isValidReading(float temperatureC, float humidityPercent) {
  return std::isfinite(temperatureC) && std::isfinite(humidityPercent) &&
         humidityPercent >= 0.0F && humidityPercent <= 100.0F;
}
