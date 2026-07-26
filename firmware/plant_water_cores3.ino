/*
 * ═══════════════════════════════════════════════════════════
 *  식물 생장 모니터링 — 급수 노드 (M5Stack Core S3 + Unit Watering U101)
 *
 *  이 노드는 화분 하나를 담당하고, 그 안에서 제어가 완결됩니다.
 *  -> WiFi/브로커가 죽어도 급수는 계속됩니다. 잃는 건 로그뿐.
 *
 *  Port B (Core S3, G8/G9) : G8=흰색 Analog(토양수분) / G9=노랑 PUMP_EN  [실측 확정]
 *  발행   : plant/<nodeId>/soil  (5분 평균)
 *           plant/<nodeId>/pump  (급수 이벤트)
 *
 *  Safety : hysteresis / dose+soak+verify / daily cap / fail-safe OFF
 * ═══════════════════════════════════════════════════════════
 */
#include <M5Unified.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>

// ══════════ 사용자 설정 ══════════
const char* WIFI_SSID = "your-hotspot";
const char* WIFI_PASS = "your-password";
const char* BROKER    = "192.168.0.15";     // ★ PC의 IPv4
const int   PORT      = 1883;

const char* PLANT_ID  = "p1";               // ★ 화분 번호 (노드마다 다르게)
const char* TREAT     = "stable";           // ★ "stable" 또는 "fluct" — 다른 값은 대시보드가 거부

// ★ 실측 확정: Core S3 Port B — PUMP=G9, SOIL=G8
const int PIN_SOIL = 8;                     // 흰색 Analog Output (실측 확정)
const int PIN_PUMP = 9;                     // 노랑 PUMP_EN   (실측 확정)

// ★ 보정①의 결과로 교체 — 절대 그대로 쓰지 말 것
const int SOIL_DRY = 2133;                  // ★ 실측으로 교체 (공기 중 또는 마른 흙)
const int SOIL_WET = 1750;                  // ★ 실측으로 교체 (충분 급수 + 5분 배수)

// ★ 처리 밴드 — 6대의 코드는 전부 같고 이 두 줄만 다름 = 곧 실험의 처리 조건
//   널뜀군 : ON_BELOW=시드는지점+여유  /  OFF_AT=포장용수량 바로 아래  (폭 최대)
//   꾸준군 : 널뜀군의 '실측 평균'을 중심으로 폭 최소 (예: 33 / 36)
int RAW_ON  = 2020;                         // ★ raw 로 직접. 이보다 크면(=마르면) 시작
int RAW_OFF = 1820;                         // ★ 이보다 작으면(=젖으면) 정지
//   두 처리군의 <중심>이 같아야 합니다 — 폭만 다르게: (RAW_ON+RAW_OFF)/2 를 맞추세요
const int MAX_DOSE_PER_FILL = 8;            // 한 번 채우는 데 최대 급수 횟수 (안전)

const unsigned long DOSE_MS = 3000;         // ★ 보정②의 결과로 교체
const unsigned long SOAK_MS = 1200000UL;    // 20분 — 절대 줄이지 말 것
const float MIN_RISE  = 2.0;                // % 미만이면 급수 실패로 간주
const int   DAILY_MAX = 6;

const int PUBLISH_MIN = 5;
const unsigned long SAMPLE_MS = 10000;
// ════════════════════════════════

WiFiClient net;
PubSubClient client(net);

String nodeId, tSoil, tPump;
double sSoil = 0; int n = 0;
bool timeOK = false;
long curBucket = -1;
unsigned long lastSample = 0;

// ── 급수 상태기계 ──
uint8_t  st = 0;                            // 0=DRYING 1=DOSING 2=SOAKING
int      nFill = 0;                         // 이번 '채움'에서 급수한 횟수
unsigned long tMark = 0;
float    before = 0, lastSoil = 0;
int      nToday = 0;
int      curDay = -1;
bool     armed = true;

void makeNodeId() {
  byte mac[6]; WiFi.macAddress(mac);
  char id[16];
  snprintf(id, sizeof(id), "wtr_%02X%02X%02X", mac[3], mac[4], mac[5]);
  nodeId = String(id);
  tSoil  = "plant/" + nodeId + "/soil";
  tPump  = "plant/" + nodeId + "/pump";
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) delay(500);
}

void connectBroker() {
  int tries = 0;
  while (!client.connected() && tries++ < 3) {     // 3회만 — 급수를 막지 않도록
    connectWiFi();
    String cid = nodeId + "-" + String(random(0xffff), HEX);
    if (client.connect(cid.c_str())) { Serial.println("MQTT OK"); return; }
    Serial.print("MQTT rc="); Serial.println(client.state());
    delay(1000);
  }
}

void syncTime() {
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  struct tm ti;
  unsigned long t0 = millis();
  while (!getLocalTime(&ti, 500) && millis() - t0 < 10000) delay(100);
  timeOK = getLocalTime(&ti, 500);
  Serial.println(timeOK ? "NTP OK" : "NTP FAIL");
}

long nowEpoch() { time_t t; time(&t); return (long)t; }

String epochToStr(long e) {
  time_t t = (time_t)e; struct tm ti; gmtime_r(&t, &ti);
  char b[32]; strftime(b, sizeof(b), "%Y-%m-%d %H:%M:%S", &ti);
  return String(b);
}

// 정전용량식: 젖을수록 ADC가 낮아짐 -> 반전 매핑
float soilPct(int raw) {
  float p = (float)(SOIL_DRY - raw) * 100.0f / (float)(SOIL_DRY - SOIL_WET);
  if (p < 0) p = 0;
  if (p > 100) p = 100;
  return p;
}

void publishPump(float aft, const char* reason) {
  char p[288];
  String ts = timeOK ? epochToStr(nowEpoch()) : String("");
  snprintf(p, sizeof(p),
    "{\"node\":\"%s\",\"plant_id\":\"%s\",\"treat\":\"%s\",\"t\":\"%s\","
    "\"dur_ms\":%lu,\"soil_before\":%.1f,\"soil_after\":%.1f,\"reason\":\"%s\"}",
    nodeId.c_str(), PLANT_ID, TREAT, ts.c_str(),
    (unsigned long)nFill * DOSE_MS, before, aft, reason);   // 채움 1회 총 급수시간
  client.publish(tPump.c_str(), p, true);   // retained: 마지막 급수 상태 보존
  Serial.print("PUMP: "); Serial.println(p);
}

// 하루 경계 (UTC 기준 — DB와 일치)
void rollDay() {
  if (!timeOK) return;
  int d = (int)(nowEpoch() / 86400L);
  if (d != curDay) { curDay = d; nToday = 0; }
}

void startDose(unsigned long now) {
  nToday++; nFill++;
  digitalWrite(PIN_PUMP, HIGH); tMark = now; st = 1;
}

void pumpTick(float soil) {
  unsigned long now = millis();
  lastSoil = soil;
  switch (st) {
    case 0:                                        // DRYING — 마르길 기다림
      if (!armed || nToday >= DAILY_MAX) break;
      if (soil < ON_BELOW) {
        before = soil; nFill = 0; startDose(now);
        Serial.printf("[fill] soil %.1f%% < %.1f%% -> 목표 %.1f%%\n",
                      soil, ON_BELOW, OFF_AT);
      }
      break;

    case 1:                                        // DOSING
      if (now - tMark >= DOSE_MS) {
        digitalWrite(PIN_PUMP, LOW); tMark = now; st = 2;
      }
      break;

    case 2:                                        // SOAKING -> 판정
      if (now - tMark < SOAK_MS) break;

      if (soil - before < MIN_RISE) {              // 튜브 빠짐/물통 빔/펌프 고장
        armed = false;
        Serial.printf("[!!] VERIFY FAIL %.1f -> %.1f -- 무장해제\n", before, soil);
        publishPump(soil, "verify_fail");
        st = 0; break;
      }

      if (soil < OFF_AT && nFill < MAX_DOSE_PER_FILL) {
        before = soil; startDose(now);             // ★ 목표까지 반복
        Serial.printf("[dose %d] %.1f%% -> 계속\n", nFill, soil);
      } else {
        Serial.printf("[done] %.1f%% (급수 %d회) -- 이제 마르게 둠\n", soil, nFill);
        publishPump(soil, "filled");               // ★ 도달 -> 손 떼고 마르게 둠
        st = 0;
      }
      break;
  }
}

void publishSoil(long bucket) {
  if (n <= 0) return;
  char p[224];
  String ts = timeOK ? epochToStr(bucket) : String("");
  snprintf(p, sizeof(p),
    "{\"node\":\"%s\",\"plant_id\":\"%s\",\"treat\":\"%s\",\"t\":\"%s\","
    "\"pct\":%.1f,\"n\":%d}",
    nodeId.c_str(), PLANT_ID, TREAT, ts.c_str(), sSoil / n, n);
  client.publish(tSoil.c_str(), p);
  Serial.print("PUB: "); Serial.println(p);
}

void drawScreen() {
  const char* S[] = {"DRY ", "DOSE", "SOAK"};
  M5.Display.setCursor(0, 0);
  M5.Display.setTextSize(3);
  M5.Display.printf("%s / %s\n\n", PLANT_ID, TREAT);
  M5.Display.printf("%5.1f %%\n\n", lastSoil);
  M5.Display.setTextSize(2);
  M5.Display.printf("band %.0f-%.0f\n", ON_BELOW, OFF_AT);
  M5.Display.printf("%s  today %d\n", S[st], nToday);
  M5.Display.printf("%s %s\n", armed ? "ARMED " : "DISARM",
                    client.connected() ? "MQTT" : "----");
}

void setup() {
  // ★ 무엇보다 먼저 — 부팅 중 펌프가 도는 것을 막음
  pinMode(PIN_PUMP, OUTPUT);
  digitalWrite(PIN_PUMP, LOW);

  auto cfg = M5.config();
  M5.begin(cfg);
  M5.Display.setTextColor(CYAN, BLACK);
  Serial.begin(115200);

  analogReadResolution(12);
  pinMode(PIN_SOIL, INPUT);

  connectWiFi();
  makeNodeId();
  syncTime();
  rollDay();
  client.setServer(BROKER, PORT);
  connectBroker();

  Serial.printf("Node : %s  (%s / %s)\n", nodeId.c_str(), PLANT_ID, TREAT);
  Serial.printf("Band : %.1f - %.1f %%\n", ON_BELOW, OFF_AT);
  if (timeOK) { long s = PUBLISH_MIN * 60L; curBucket = (nowEpoch() / s) * s; }
}

void loop() {
  M5.update();
  // 브로커가 없어도 급수는 계속되어야 함 -> 재연결이 루프를 막지 않게
  if (!client.connected()) {
    static unsigned long lastTry = 0;
    if (millis() - lastTry > 30000) { lastTry = millis(); connectBroker(); }
  }
  client.loop();
  rollDay();

  unsigned long now = millis();
  if (now - lastSample >= SAMPLE_MS) {
    lastSample = now;
    float soil = soilPct(analogRead(PIN_SOIL));
    sSoil += soil; n++;
    pumpTick(soil);                              // 5분 평균이 아니라 현재값으로
    drawScreen();
  }

  long s = PUBLISH_MIN * 60L;
  if (timeOK) {
    long bucket = (nowEpoch() / s) * s;
    if (curBucket < 0) curBucket = bucket;
    if (bucket != curBucket) {
      publishSoil(curBucket); sSoil = 0; n = 0; curBucket = bucket;
    }
  } else {
    static unsigned long lastPub = 0;
    if (now - lastPub >= (unsigned long)PUBLISH_MIN * 60000UL) {
      lastPub = now; publishSoil(0); sSoil = 0; n = 0;
    }
  }
  delay(20);
}
