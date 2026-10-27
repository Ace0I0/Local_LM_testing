#include <cassert>

#include "mqtt_sensor_validation.h"

int main() {
  assert(isValidReading(21.5F, 45.0F));
  assert(!isValidReading(NAN, 45.0F));
  assert(!isValidReading(21.5F, NAN));
  assert(!isValidReading(21.5F, 100.1F));
}
