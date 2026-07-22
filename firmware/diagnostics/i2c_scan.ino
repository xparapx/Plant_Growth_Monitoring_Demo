#include <Wire.h>

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 3000) {}   // R4: USB 시리얼 준비 대기
  Wire.begin();                           // R4 + Base Shield (SDA/SCL 고정)
  delay(500);
  Serial.println("I2C scan...");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { Serial.print("  found 0x"); Serial.println(a, HEX); }
  }
  Serial.println("done. expect 0x76=BME688, 0x62=SCD41, 0x23=DLight, 0x33=MLX90640");
}
void loop() {}
