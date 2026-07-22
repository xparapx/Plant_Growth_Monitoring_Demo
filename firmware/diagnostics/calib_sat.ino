/* 조금 붓고 -> 기다리고 -> 재기를 반복. 더 안 오르면 = 포화.
 * ★ '연속 공급'이 아니라 '버스트 + 대기'인 이유:
 *   센서는 화분의 한 지점에만 있어 물이 도달하는 데 몇 분 걸립니다.
 *   연속으로 부으면 그동안 값이 안 움직여 '평탄하다'고 오판하거나,
 *   타임아웃을 길게 잡으면 그동안 계속 부어 넘칩니다.
 */
#include <M5Unified.h>
const int  PIN_PUMP = 9;                  // 실측 확정: PUMP_EN = G9
const int  PIN_SOIL = 8;                  // 실측 확정: Analog = G8
const int  SOIL_DRY = 3200, SOIL_WET = 1400;   // ★ DRY/WET 보정값으로 교체

const float         EPS       = 1.0;      // %p — 센서 잡음의 3배 이상
const unsigned long BURST_MS  = 2000;
const unsigned long WAIT_MS   = 300000;   // 5분 — 물이 센서까지 도달할 시간
const int           MAX_BURST = 30;       // 안전 상한

float soilPct(int raw) {
  float v = 100.0f * (SOIL_DRY - raw) / (float)(SOIL_DRY - SOIL_WET);
  return v < 0 ? 0 : (v > 100 ? 100 : v);
}

void setup() {
  auto cfg = M5.config(); M5.begin(cfg);
  pinMode(PIN_PUMP, OUTPUT); digitalWrite(PIN_PUMP, LOW);
  Serial.begin(115200);
  analogReadResolution(12);

  float before = soilPct(analogRead(PIN_SOIL));
  for (int i = 1; i <= MAX_BURST; i++) {
    digitalWrite(PIN_PUMP, HIGH); delay(BURST_MS);
    digitalWrite(PIN_PUMP, LOW);
    delay(WAIT_MS);                                  // ★ 도달 대기 — 없으면 오판
    float after = soilPct(analogRead(PIN_SOIL));
    Serial.printf("burst %2d : %.1f -> %.1f  (+%.1f)\n", i, before, after, after-before);
    if (after - before < EPS) {
      Serial.printf("\n>> 포화 = %.1f%%   => 상한(OFF_AT) = %.1f%%\n", after, after - 15.0);
      break;
    }
    before = after;
  }
}
void loop() {}
