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
 *  ★ 2026-09 개정 — water_node.ino 에서 배운 것들을 이식
 *    · 재접속이 <절대 기다리지 않음> — 예전 판은 끊길 때마다 최대 85초
 *      루프가 멈춰 샘플이 통째로 빠졌습니다. 이제 10초에 한 번, 1회만 시도.
 *    · 발행 실패 = 유실이던 것을 오프라인 큐(8건)로 — 타임스탬프는
 *      payload 에 이미 박혀 있으므로 늦게 발행돼도 시각이 안 밀립니다.
 *    · String 제거(힙 단편화) · WDT(5초) · NTP 하루 1회 재동기화.
 *    · 촬영 조명 — RGB 네오픽셀 4구 × 2 (핀 8·9), KST 05:45~06:15 시간
 *      기반 점등 + 원격 제어(MQTT plant/<id>/light/set "1"/"0", 30분
 *      자동 소등) + 시리얼 1/0 테스트 (USE_LIGHT=1).
 * ═══════════════════════════════════════════════════════════
 *  ★ Core S3 판과 다른 점 (R4 WiFi 전용)
 *    · M5Unified 없음 → 화면 코드 제거 (R4는 12x8 LED 매트릭스뿐)
 *    · WiFi 라이브러리 = WiFiS3 (ESP32 아님)
 *    · Wire.begin() — 핀 번호 지정 안 함 (SDA/SCL 고정)
 *    · NTP = RTC(WiFiS3 내장) 이용, UTC
 *  라이브러리: WiFiS3(보드 내장) / PubSubClient / Sensirion I2C SCD4x(신버전)
 *              Adafruit BME680(BME688 호환) / BH1750 / Adafruit NeoPixel
 * ═══════════════════════════════════════════════════════════
 */
#include <WiFiS3.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <SensirionI2cScd4x.h>          // 신버전: I2c 소문자
#include <Adafruit_BME680.h>
#include <BH1750.h>
#include <RTC.h>                         // R4 내장 RTC (NTP 시각 보관)
#include <WDT.h>                         // R4 내장 워치독

#ifdef NO_ERROR                          // SCD4x 신버전 매크로 충돌 방지
#undef NO_ERROR
#endif
#define NO_ERROR 0
const uint8_t SCD41_ADDR = 0x62;

// ══════════ 사용자 설정 ══════════
const char* WIFI_SSID = "your-hotspot";       // ★ 2.4GHz SSID
const char* WIFI_PASS = "your-password";
const char* BROKER    = "192.168.0.15";     // ★ 브로커 IP — 파이 확정 후 교체 (Pi: hostname -I / PC: ipconfig)
const int   PORT      = 1883;

const uint16_t ALTITUDE_M = 40;             // ★ 학교 해발고도(m) — SCD41 CO2 보정
const int   PUBLISH_MIN = 5;
const unsigned long SAMPLE_MS = 10000;      // 5분에 n≈30
// NTP는 UTC로 저장, hub에서 +9h. 아래 KST 는 조명 창 계산에만 씁니다.
// ════════════════════════════════

// ══════════ 촬영 조명 — RGB 네오픽셀 4구 × 2 (핀 8·9) ══════════
// 네오픽셀은 LED마다 드라이버 내장 -> 데이터 핀 직결, 릴레이/MOSFET 불요.
//   · 기본 동작은 시간 기반 독립 점등 — 창(05:45~06:15)이 최우선이고,
//     창 점등은 어떤 명령으로도 못 끕니다 (실험 데이터 보호).
//   · 원격 제어: MQTT plant/<id>/light/set 에 "1"/"0" (또는 on/off).
//     시리얼 모니터 1/0 도 같은 효과. 둘 다 <명령 점등>으로 취급되어
//     LIGHT_CMD_MAX_MS 뒤 자동 소등 — 켜 두고 잊어도 남지 않습니다.
//   · 상태 보고: 바뀔 때마다 plant/<id>/light 로 {"state":..,"by":..} 발행.
//   · NTP 실패(timeOK=false)면 창 점등은 하지 않음 (안전측).
//   · 전류: 풀 화이트 LED당 ~60mA -> 8구 풀밝기 ~480mA. 화면 밝기·USB 전원
//     여유를 확인하고, 부족 징후(리셋·색 틀어짐)가 보이면 별도 5V 급전.
//   · RGB 합성 백색은 스펙트럼이 뾰족함 — 설치 후 새벽 시험 촬영으로
//     ExG 마스크가 안정한지 확인할 것 (매뉴얼 패널 19).
#define USE_LIGHT 1
#if USE_LIGHT
  #include <Adafruit_NeoPixel.h>
  const int     LIGHT_PIN1   = 8;           // ★ 스트립 1 데이터 핀
  const int     LIGHT_PIN2   = 9;           // ★ 스트립 2 데이터 핀
  const int     LIGHT_N      = 4;           // ★ 스트립당 LED 개수
  const uint8_t LIGHT_BRIGHT = 255;         // 0~255 — 매일 같은 값으로 고정 (전류 제한 겸)
  const long    LIGHT_ON_S   = 5*3600L + 45*60L;   // KST 05:45
  const long    LIGHT_OFF_S  = 6*3600L + 15*60L;   // KST 06:15 (촬영 05:50 이 창 안)
  const unsigned long LIGHT_CMD_MAX_MS = 1800000UL;   // 명령 점등 자동 소등 (30분)
  Adafruit_NeoPixel strip1(LIGHT_N, LIGHT_PIN1, NEO_GRB + NEO_KHZ800);  // RGB (백색 칩 없음)
  Adafruit_NeoPixel strip2(LIGHT_N, LIGHT_PIN2, NEO_GRB + NEO_KHZ800);
  bool lit = false;                         // 현재 실제 상태
  bool cmdOn = false;                       // 원격/시리얼 명령 점등 중
  unsigned long tCmd = 0;                   // 명령 점등 시작 시각
  const char* litBy = "off";                // "window" | "cmd" | "off" — 상태 보고용

  void setLight(bool on) {                  // 점등/소등 한 곳에서 — RGB 합성 백색
    uint32_t c = on ? Adafruit_NeoPixel::Color(255, 255, 255) : 0;
    for (int i = 0; i < LIGHT_N; i++) { strip1.setPixelColor(i, c); strip2.setPixelColor(i, c); }
    strip1.show(); strip2.show();
  }
#endif

WiFiClient net;
PubSubClient client(net);
SensirionI2cScd4x scd4x;                 // 신버전 클래스명
Adafruit_BME680  bme;
BH1750           lightMeter;

char nodeId[16] = "env_boot";            // MAC 확보 전 임시 — WiFi 붙으면 확정
char topic[32]  = "plant/env_boot/env";
bool idReady = false;

double sT=0, sH=0, sP=0, sV=0, sL=0, sC=0;
int n=0, nC=0, nB=0;
bool bmeOK=false, scdOK=false, luxOK=false, timeOK=false;
long curBucket = -1;
unsigned long lastSample = 0;
int failStreak = 0;
const int FAIL_LIMIT = 12;

// ── 네트워크 재시도·재동기화 ──
const unsigned long RETRY_MS  = 10000UL;    // WiFi/MQTT/NTP 재시도 간격
const unsigned long RESYNC_S  = 86400L;     // NTP 재동기화 주기 (RTC 드리프트 보정)
unsigned long tRetry = 0, tNtp = 0;
long lastSyncEpoch = 0;

// ── 오프라인 큐 — 발행 실패한 5분 평균을 담아 두었다 되는 대로 flush ──
//    payload 에 버킷 시각이 들어 있어 늦게 발행돼도 데이터 시각은 정확합니다.
const int QUEUE_MAX = 8;                    // 8건 = 40분 치. 넘치면 오래된 것부터 버림
char pq[QUEUE_MAX][224];
int  pqHead = 0, pqCount = 0;

// ── VPD — 습도가 아니라 이것이 증산을(=마르는 속도를) 정함 ──
float esat(float t)            { return 0.6108f * expf(17.27f*t/(t+237.3f)); }   // kPa
float vpdOf(float t, float rh) { return esat(t) * (1.0f - rh/100.0f); }          // kPa

// R4는 MAC을 WiFi.macAddress()로 얻음 (연결 후에 확정)
void makeNodeId() {
  byte mac[6]; WiFi.macAddress(mac);
  snprintf(nodeId, sizeof(nodeId), "env_%02X%02X%02X", mac[3], mac[4], mac[5]);
  snprintf(topic, sizeof(topic), "plant/%s/env", nodeId);
  idReady = true;
  Serial.print("Node : "); Serial.println(nodeId);
  Serial.print("Topic: "); Serial.println(topic);
}

// ★ 절대 기다리지 않습니다 — 끊겨 있으면 10초에 한 번, 1회만 시도.
//   (예전 판은 while+delay 로 최대 85초 루프가 멈춰 샘플이 빠졌습니다)
bool netReady() {
  if (WiFi.status() != WL_CONNECTED) {
    unsigned long now = millis();
    if (now - tRetry >= RETRY_MS) { tRetry = now; WiFi.begin(WIFI_SSID, WIFI_PASS); }
    return false;
  }
  if (!idReady) makeNodeId();
  if (client.connected()) return true;
  unsigned long now = millis();
  if (now - tRetry < RETRY_MS) return false;
  tRetry = now;
  char cid[24];
  snprintf(cid, sizeof(cid), "%s-%04x", nodeId, (unsigned)random(0xffff));
  if (client.connect(cid)) {
    Serial.println("MQTT OK");
#if USE_LIGHT
    char sub[48];
    snprintf(sub, sizeof(sub), "plant/%s/light/set", nodeId);
    client.subscribe(sub);                       // 원격 점등 명령 구독 (노드 지정)
    client.subscribe("plant/light/set");         // 브로드캐스트 — 웹 UI 조명 버튼용
    publishLightState();                         // 재접속 시 현재 상태 알림
#endif
    return true;
  }
  Serial.print("MQTT rc="); Serial.println(client.state());   // -2 = 거부/방화벽
  return false;
}

// NTP → 내장 RTC (UTC epoch). 논블로킹 — 될 때까지 10초 간격으로 시도,
// 성공 후에도 하루 한 번 다시 받아 RTC 드리프트를 지웁니다.
void ntpTick() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (timeOK) {
    RTCTime t; RTC.getTime(t);
    if ((long)t.getUnixTime() - lastSyncEpoch < RESYNC_S) return;   // 아직 재동기화 때가 아님
  }
  unsigned long now = millis();
  if (now - tNtp < RETRY_MS) return;
  tNtp = now;
  unsigned long epoch = WiFi.getTime();         // 실패 시 0 (블로킹 없음)
  if (!epoch) { if (!timeOK) Serial.println("NTP 대기중"); return; }
  RTC.begin();
  RTCTime rt((time_t)epoch);
  RTC.setTime(rt);
  lastSyncEpoch = (long)epoch;
  if (!timeOK) Serial.println("NTP OK");
  timeOK = true;
}

long nowEpoch() {
  if (!timeOK) return 0;
  RTCTime t; RTC.getTime(t); return (long)t.getUnixTime();
}

void epochToStr(long e, char* out, size_t len) {
  time_t t=(time_t)e; struct tm ti; gmtime_r(&t, &ti);
  strftime(out, len, "%Y-%m-%d %H:%M:%S", &ti);
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

void enqueuePayload(const char* p) {
  int i = (pqHead + pqCount) % QUEUE_MAX;
  if (pqCount == QUEUE_MAX) { pqHead = (pqHead + 1) % QUEUE_MAX; pqCount--; }  // 오래된 것부터 버림
  strncpy(pq[i], p, sizeof(pq[i]) - 1);
  pq[i][sizeof(pq[i]) - 1] = 0;
  pqCount++;
}

void flushQueue() {
  while (pqCount > 0) {
    if (!client.publish(topic, pq[pqHead])) return;   // 실패하면 다음 기회에
    Serial.print("PUB(late): "); Serial.println(pq[pqHead]);
    pqHead = (pqHead + 1) % QUEUE_MAX; pqCount--;
  }
}

void publishAverage(long bucket) {
  if (n <= 0) return;
  int cb = nB > 0 ? nB : 1;
  int cc = nC > 0 ? nC : 1;
  char ts[24] = "";
  if (timeOK) epochToStr(bucket, ts, sizeof(ts));
  char p[224];
  snprintf(p, sizeof(p),
    "{\"node\":\"%s\",\"t\":\"%s\",\"temp\":%.2f,\"hum\":%.2f,"
    "\"press\":%.1f,\"vpd\":%.3f,\"lux\":%.1f,\"co2\":%.1f,\"n\":%d}",
    nodeId, ts, sT/cb, sH/cb, sP/cb, sV/cb, sL/n, sC/cc, n);
  // ★ 먼저 담고, 발행은 되는 대로 — 끊겨 있어도 5분 평균이 유실되지 않습니다
  enqueuePayload(p);
  if (client.connected()) flushQueue();
  else Serial.print("QUEUED: "), Serial.println(p);
}

void resetAccum() { sT=sH=sP=sV=sL=sC=0; n=0; nC=0; nB=0; }

#if USE_LIGHT
// 상태 보고 — 바뀔 때만 발행. 끊겨 있으면 조용히 넘어감(조명은 로컬이 진실).
void publishLightState() {
  if (!client.connected() || !idReady) return;
  char t[48], m[96];
  snprintf(t, sizeof(t), "plant/%s/light", nodeId);
  snprintf(m, sizeof(m), "{\"node\":\"%s\",\"state\":\"%s\",\"by\":\"%s\"}",
           nodeId, lit ? "on" : "off", litBy);
  client.publish(t, m);
}

// 원격/시리얼 <명령 점등> 공통 진입점. 켜기는 워치독 타이머를 재장전한다.
void lightCommand(bool on, const char* src) {
  cmdOn = on;
  if (on) tCmd = millis();
  Serial.print("[LIGHT] cmd "); Serial.print(on ? "ON" : "OFF");
  Serial.print(" ("); Serial.print(src); Serial.println(")");
}

// 점등 결정 — 매 루프 재평가. 창이 최우선, 명령 점등은 30분 워치독.
void lightTick() {
  bool window = false;
  long e = nowEpoch();
  if (e > 0) {
    long sod = (e + 9*3600L) % 86400L;          // KST 자정 기준 초 (UTC 일경계 wrap 처리)
    window = (sod >= LIGHT_ON_S && sod < LIGHT_OFF_S);
  }                                             // timeOK=false -> 창 점등 없음 (안전측)
  if (cmdOn && millis() - tCmd >= LIGHT_CMD_MAX_MS) {   // 명령 점등 워치독
    cmdOn = false;
    Serial.println("[LIGHT] cmd timeout — auto off");
  }
  bool want = window || cmdOn;
  if (want == lit) return;
  lit = want;
  litBy = lit ? (window ? "window" : "cmd") : "off";
  setLight(lit);
  Serial.print("[LIGHT] "); Serial.print(lit ? "on" : "off");
  Serial.print(" by "); Serial.println(litBy);
  publishLightState();
}

// 시리얼 테스트: 모니터(115200)에서 1 = 켜기, 0 = 끄기.
void lightSerialTest() {
  if (!Serial.available()) return;
  char ch = Serial.read();
  if (ch == '1' || ch == '0') lightCommand(ch == '1', "serial");
}
#endif

// MQTT 수신 — plant/<id>/light/set : "1"/"on" 켜기, "0"/"off" 끄기
void onMqtt(char* t, byte* payload, unsigned int len) {
#if USE_LIGHT
  const char* slash = strrchr(t, '/');
  if (slash == nullptr || strcmp(slash, "/set") != 0) return;
  char v[8] = "";
  strncpy(v, (const char*)payload, len < sizeof(v) - 1 ? len : sizeof(v) - 1);
  if (!strcmp(v, "1") || !strcasecmp(v, "on"))  lightCommand(true, "mqtt");
  if (!strcmp(v, "0") || !strcasecmp(v, "off")) lightCommand(false, "mqtt");
#endif
}

void setup() {
  Serial.begin(115200);
  Wire.begin();                            // R4 : Base Shield I2C (SDA/SCL 고정)
  initSensors();

#if USE_LIGHT
  strip1.begin(); strip2.begin();
  strip1.setBrightness(LIGHT_BRIGHT);      // 매일 같은 값 — 전류 제한 겸 조명 고정
  strip2.setBrightness(LIGHT_BRIGHT);
  strip1.clear(); strip1.show();           // 부팅은 반드시 소등으로
  strip2.clear(); strip2.show();
#endif

  // ★ 여기서 기다리지 않습니다 — 연결·NTP·nodeId 확정은 전부 loop 에서 논블로킹으로.
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  client.setServer(BROKER, PORT);
  client.setCallback(onMqtt);              // 원격 점등 명령 수신
  client.setKeepAlive(60);

  WDT.begin(5000);                         // 5초 워치독 — I2C/소켓이 얼면 리셋
  Serial.println("[BOOT] env node — 논블로킹 접속, 큐 8건, WDT 5s, LIGHT 4구x2 핀8·9 (mqtt/serial 제어)");
}

void loop() {
  WDT.refresh();

  if (netReady()) { client.loop(); flushQueue(); }
  ntpTick();
#if USE_LIGHT
  lightSerialTest();
  lightTick();
#endif

  if (failStreak >= FAIL_LIMIT) recoverI2C();

  unsigned long now = millis();
  long s = PUBLISH_MIN * 60L;

  if (timeOK) {
    long bucket = (nowEpoch()/s)*s;
    if (curBucket < 0) { curBucket = bucket; }
    if (bucket != curBucket) { publishAverage(curBucket); resetAccum(); curBucket = bucket; }
  } else {
    static unsigned long lastPub = 0;
    if (now - lastPub >= (unsigned long)PUBLISH_MIN*60000UL) { lastPub = now; publishAverage(0); resetAccum(); }
  }

  if (now - lastSample >= SAMPLE_MS) { lastSample = now; takeSample(); }
  delay(20);
}
