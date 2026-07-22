#include <M5Unified.h>
const int PIN_PUMP = 9;               // ★ 실측 확정: PUMP_EN = G9
void setup() {
  auto cfg = M5.config(); M5.begin(cfg);
  Serial.begin(115200);
  pinMode(PIN_PUMP, OUTPUT);
  digitalWrite(PIN_PUMP, LOW);        // 반드시 LOW부터
  delay(3000);
  Serial.println("pump ON 3s -- 전력계를 보세요");
  digitalWrite(PIN_PUMP, HIGH);
  delay(3000);
  digitalWrite(PIN_PUMP, LOW);
  Serial.println("pump OFF");
}
void loop() {}
