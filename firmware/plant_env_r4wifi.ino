/*
 * ═══════════════════════════════════════════════════════════
 *  식물 생장 모니터링 — 환경 노드 (Arduino UNO R4 WiFi)   [데모판]
 *
 *  Grove Base Shield V2 — I2C 포트 4개. 허브 없이 하나씩 꽂음
 *    BME688  0x76 : 온도·습도·기압  <- 대표값. 가스히터 OFF. VPD 계산
 *    SCD41   0x62 : CO2 전용 (내장 온습도는 사용하지 않음)
 *    DLight  0x23 : 조도 (lux)
 *    MLX90640 0x33: 2단계
 *  Base Shield 전원 스위치는 반드시 5V 위치.
 *
 *  전송 : plant/<nodeId>/env    NTP(UTC) 정각 격자 5분 평균
 * ═══════════════════════════════════════════════════════════
 *  ★ Core S3 판과 다른 점 (R4 WiFi 전용)
 *    · M5Unified 없음 → 화면 코드 제거 (R4는 12x8 LED 매트릭스뿐)
 *    · WiFi 라이브러리 = WiFiS3 (ESP32 아님)
 *    · Wire.begin() — 핀 번호 지정 안 함 (SDA/SCL 고정)
 *    · NTP = RTC(WiFiS3 내장) 이용, UTC
 *    · 센서 라이브러리·MQTT·타당성 게이트·평균 로직은 그대로
 *  라이브러리: WiFiS3(보드 내장) / PubSubClient / Sensirion I2C SCD4x(신버전)
 *              Adafruit BME680(BME688 호환) / BH1750
 * ═══════════════════════════════════════════════════════════
 */
#include <WiFiS3.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <SensirionI2cScd4x.h>          // 신버전: I2c 소문자
#include <Adafruit_BME680.h>
#include <BH1750.h>
#include <RTC.h>                         // R4 내장 RTC (NTP 시각 보관)

#ifdef NO_ERROR                          // SCD4x 신버전 매크로 충돌 방지
#undef NO_ERROR
#endif
#define NO_ERROR 0
const uint8_t SCD41_ADDR = 0x62;

// ══════════ 사용자 설정 ══════════
const char* WIFI_SSID = "your-hotspot";
const char* WIFI_PASS = "your-password";
const char* BROKER    = "192.168.0.15";     // ★ PC의 IPv4 (ipconfig) → Pi 도착 후 교체
const int   PORT      = 1883;

const uint16_t ALTITUDE_M = 40;             // ★ 학교 해발고도(m) — SCD41 CO2 보정
const int   PUBLISH_MIN = 5;
const unsigned long SAMPLE_MS = 10000;      // 5분에 n≈30
const long  TZ_OFFSET = 0;                  // NTP는 UTC로 저장 (hub에서 +9h)
// ════════════════════════════════

WiFiClient net;
PubSubClient client(net);
SensirionI2cScd4x scd4x;                 // 신버전 클래스명
Adafruit_BME680  bme;
BH1750           lightMeter;

String nodeId, topic;
double sT=0, sH=0, sP=0, sV=0, sL=0, sC=0;
int n=0, nC=0, nB=0;
bool bmeOK=false, scdOK=false, luxOK=false, timeOK=false;
long curBucket = -1;
unsigned long lastSample = 0;
int failStreak = 0;
const int FAIL_LIMIT = 12;

// ── VPD — 습도가 아니라 이것이 증산을(=마르는 속도를) 정함 ──
float esat(float t)            { return 0.6108f * expf(17.27f*t/(t+237.3f)); }   // kPa
float vpdOf(float t, float rh) { return esat(t) * (1.0f - rh/100.0f); }          // kPa

// R4는 MAC을 WiFi.macAddress()로 얻음 (연결 후)
void makeNodeId() {
  byte mac[6]; WiFi.macAddress(mac);
  char id[16];
  snprintf(id, sizeof(id), "env_%02X%02X%02X", mac[3], mac[4], mac[5]);
  nodeId = String(id);
  topic  = "plant/" + nodeId + "/env";
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis()-t0 < 15000) { delay(500); Serial.print("."); }
  Serial.println(WiFi.status()==WL_CONNECTED ? " OK" : " FAIL");
}

void connectBroker() {
  int tries = 0;
  while (!client.connected() && tries++ < 5) {
    connectWiFi();
    String cid = nodeId + "-" + String(random(0xffff), HEX);
    Serial.print("MQTT");
    if (client.connect(cid.c_str())) { Serial.println(" OK"); return; }
    Serial.print(" rc="); Serial.println(client.state());   // -2 = 거부/방화벽
    delay(2000);
  }
}

// R4 WiFi는 NTP를 WiFi.getTime()으로 받아 내장 RTC에 심음 (UTC epoch)
void syncTime() {
  Serial.print("NTP");
  unsigned long epoch = 0, t0 = millis();
  while (epoch == 0 && millis()-t0 < 10000) { epoch = WiFi.getTime(); delay(500); Serial.print("."); }
  if (epoch) {
    RTC.begin();
    RTCTime now((time_t)epoch);
    RTC.setTime(now);
    timeOK = true;  Serial.println(" OK");
  } else { timeOK = false; Serial.println(" FAIL -> 정각정렬 없이 동작"); }
}

long nowEpoch() {
  if (!timeOK) return 0;
  RTCTime t; RTC.getTime(t); return (long)t.getUnixTime();
}

String epochToStr(long e) {
  time_t t=(time_t)e; struct tm ti; gmtime_r(&t, &ti);
  char b[32]; strftime(b, sizeof(b), "%Y-%m-%d %H:%M:%S", &ti);
  return String(b);
}

// 얼어붙은 센서가 물리적으로 불가능한 값을 반복하는 고장 모드를 차단
bool plausibleTH(float t, float h) { return t>-10 && t<60 && h>=0 && h<=100; }
bool plausibleCO2(float c)         { return c>300 && c<10000; }

void initSensors() {
  // BME688 — 대표 온습도. 가스히터는 끔(자체 발열로 온습도가 오염됨)
  bmeOK = bme.begin(0x76);
  if (!bmeOK) bmeOK = bme.begin(0x77);          // 보드에 따라 0x77
  if (bmeOK) {
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
    bme.setGasHeater(0, 0);                     // ★ OFF — VOC 쓰려면 (320,150)
  }
  Serial.println(bmeOK ? "BME688 시작" : "BME688 실패 - 0x76/0x77 확인");

  scd4x.begin(Wire, SCD41_ADDR);                // 신버전: 주소 인자 필요
  scd4x.stopPeriodicMeasurement(); delay(500);
  scd4x.setSensorAltitude(ALTITUDE_M);          // 기압 보정 (측정 정지 중에만)
  scdOK = (scd4x.startPeriodicMeasurement() == NO_ERROR);
  Serial.println(scdOK ? "SCD41 시작" : "SCD41 실패 - 0x62 확인");

  luxOK = lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  Serial.println(luxOK ? "DLight 시작" : "DLight 실패 - 0x23 확인");
}

void recoverI2C() {
  Serial.println("[RECOVER] I2C 복구");
  Wire.end(); delay(50);
  Wire.begin();                                 // R4 : 핀 지정 없음
  initSensors();
  failStreak = 0;
  if (!bmeOK && !scdOK && !luxOK) { Serial.println("[RECOVER] 실패 -> 리셋"); NVIC_SystemReset(); }
}

void takeSample() {
  bool any = false;

  // ── BME688 : 대표 온습도 + 기압 -> VPD ──
  if (bmeOK && bme.performReading()) {
    float t = bme.temperature, hm = bme.humidity, pr = bme.pressure / 100.0f;  // Pa -> hPa
    if (plausibleTH(t, hm)) { sT += t; sH += hm; sP += pr; sV += vpdOf(t, hm); nB++; any = true; }
  }

  // ── SCD41 : CO2만 사용 (온습도 t,hm은 읽고 버림) ──
  uint16_t co2=0; float t=0, hm=0; bool ready=false;
  if (scdOK && scd4x.getDataReadyStatus(ready)==NO_ERROR && ready) {   // 신버전 함수명
    if (scd4x.readMeasurement(co2, t, hm)==NO_ERROR && co2!=0 && plausibleCO2(co2)) { sC += co2; nC++; any = true; }
  }

  float lx = luxOK ? lightMeter.readLightLevel() : NAN;
  if (!isnan(lx) && lx >= 0) { sL += lx; any = true; }

  n++;
  if (any) failStreak = 0; else failStreak++;
}

void publishAverage(long bucket) {
  if (n <= 0) return;
  int cb = nB > 0 ? nB : 1;
  int cc = nC > 0 ? nC : 1;
  char p[320];
  String ts = timeOK ? epochToStr(bucket) : String("");
  snprintf(p, sizeof(p),
    "{\"node\":\"%s\",\"t\":\"%s\",\"temp\":%.2f,\"hum\":%.2f,"
    "\"press\":%.1f,\"vpd\":%.3f,\"lux\":%.1f,\"co2\":%.1f,\"n\":%d}",
    nodeId.c_str(), ts.c_str(), sT/cb, sH/cb, sP/cb, sV/cb, sL/n, sC/cc, n);
  client.publish(topic.c_str(), p);
  Serial.print("PUB: "); Serial.println(p);
}

void resetAccum() { sT=sH=sP=sV=sL=sC=0; n=0; nC=0; nB=0; }

void setup() {
  Serial.begin(115200);
  Wire.begin();                            // R4 : Base Shield I2C (SDA/SCL 고정)
  initSensors();

  connectWiFi();
  makeNodeId();
  syncTime();
  client.setServer(BROKER, PORT);
  connectBroker();

  Serial.print("Node : "); Serial.println(nodeId);
  Serial.print("Topic: "); Serial.println(topic);
  if (timeOK) { long s = PUBLISH_MIN*60L; curBucket = (nowEpoch()/s)*s; }
}

void loop() {
  if (!client.connected()) connectBroker();
  client.loop();

  if (failStreak >= FAIL_LIMIT) recoverI2C();

  unsigned long now = millis();
  long s = PUBLISH_MIN * 60L;

  if (timeOK) {
    long bucket = (nowEpoch()/s)*s;
    if (curBucket < 0) curBucket = bucket;
    if (bucket != curBucket) { publishAverage(curBucket); resetAccum(); curBucket = bucket; }
  } else {
    static unsigned long lastPub = 0;
    if (now - lastPub >= (unsigned long)PUBLISH_MIN*60000UL) { lastPub = now; publishAverage(0); resetAccum(); }
  }

  if (now - lastSample >= SAMPLE_MS) { lastSample = now; takeSample(); }
  delay(20);
}
