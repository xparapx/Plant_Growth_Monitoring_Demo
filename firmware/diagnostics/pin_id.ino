#include <M5Unified.h>
void setup() {
  auto cfg = M5.config(); M5.begin(cfg);
  Serial.begin(115200);
  analogReadResolution(12);           // 0..4095
  pinMode(8, INPUT); pinMode(9, INPUT);
}
void loop() {
  Serial.printf("G8=%4d   G9=%4d\n", analogRead(8), analogRead(9));
  delay(500);                         // 측정판을 물에 담갔다 빼며 관찰
}
