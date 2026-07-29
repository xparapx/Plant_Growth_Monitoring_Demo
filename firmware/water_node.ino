/*
  water_node.ino — 급수 노드 폐루프 (2화분 데모)
  M5Stack Core S3 + Watering Unit U101      PUMP = G9 · SOIL = G8

  ■ 펄스 급수 — 연속 급수를 하지 않는 이유 셋
      ① 넘침        700mL 화분은 한 번에 부으면 표면에 고입니다
      ② 편류        마른 배양토는 발수성이 있어 벽면 따라 바닥으로 빠집니다
      ③ 센서 지연   물이 전극까지 퍼지는 데 3~10분. 즉시 재면 과급수합니다
    -> 도즈(짧게) → 대기 → 재측정 → 필요하면 반복

  ■ 노드마다 고칠 곳은 맨 위 두 줄(TREAT_FLUCT / PLANT_ID)뿐입니다.
*/
#include <M5Unified.h>

// ══════════════ 네트워크 (0 이면 완전 오프라인) ══════════════
// ★ 급수 판단은 이 보드 안에서 끝납니다. WiFi 가 죽어도 물은 계속 줍니다.
//   MQTT 는 <보고> 통로일 뿐이라, 끊기면 잃는 것은 로그뿐입니다.
#define USE_MQTT   1

#if USE_MQTT
  #include <WiFi.h>
  #include <PubSubClient.h>
  #include <string.h>
  const char* WIFI_SSID = "your-hotspot";
  const char* WIFI_PASS = "your-password";
  const char* BROKER    = "192.168.1.33";
  const int   BROKER_PORT = 1883;
  const char* NODE_ID   = "w2";             // 급수 노드 이름 (노드마다 다르게)

  const unsigned long SOIL_PUB_MS  = 300000UL;   // 5분마다 토양수분 보고
  const unsigned long RETRY_MS     = 10000UL;    // 재접속 시도 간격
  const int  QUEUE_MAX = 12;                     // 끊겼을 때 담아두는 이벤트 수
#endif

// ══════════════ 노드 설정 — 여기만 고칩니다 ══════════════
#define TREAT_FLUCT   1                 // 0 = 꾸준군(stable) · 1 = 널뜀군(fluct)
const char* PLANT_ID = "p2";            // 화분 이름 (p1, p2, ...)

// 센서 보정 — 2026-07 실측 (공기 2133 / 포장용수량 1750)
//   ★ raw 는 젖으면 내려갑니다.  마른 흙으로 DRY 를 다시 잡으면 이 두 줄만 고치세요.
const int RAW_DRY = 2120;
const int RAW_WET = 1750;

// ══════════════ 처리군별 상수 ══════════════
//  ★ 밴드를 % 가 아니라 raw 로 직접 씁니다.
//    % 는 보정 상수(RAW_DRY/RAW_WET)를 고치면 같은 흙이 다른 숫자로 보입니다.
//    raw 는 센서가 실제로 내는 값이라 보정을 바꿔도 흙 상태가 바뀌지 않습니다.
//
//  ★ 두 처리군의 <중심>이 같아야 실험이 성립합니다 — 폭만 다릅니다.
//       stable  (1940+1900)/2 = 1920
//       fluct   (2020+1820)/2 = 1920      <- 같아야 함
//
//  관측 기준점 (2026-07)   포장용수량 1750 · 물 안 준 화분 1940 · 공기 2133
#if TREAT_FLUCT
  const char* TREAT   = "fluct";
  const int   RAW_ON  = 2020;           // 이보다 크면(=마르면) 급수 시작
  const int   RAW_OFF = 1820;           // 이보다 작으면(=젖으면) 정지
  const int   DOSE_SEED = 600;          // 첫 도즈 6mL — 이후에는 학습값으로 조절
#else
  const char* TREAT   = "stable";
  const int   RAW_ON  = 1940;
  const int   RAW_OFF = 1900;
  const int   DOSE_SEED = 300;          // 첫 도즈 3mL — 이후에는 학습값으로 조절
#endif
const int BAND_CENTER = (RAW_ON + RAW_OFF) / 2;   // 두 노드가 같은지 부팅 로그로 확인

// ══════════════ 안전·타이밍 ══════════════
// ── 적응 급수 ──────────────────────────────────────────
// 한 번 물을 주면 raw 가 몇 counts 내려가는지를 <스스로 배웁니다>.
// 그 값으로 다음 도즈 길이를 정하므로, 펌프 유량이나 흙 상태가 달라져도 따라갑니다.
//   · 목표까지 남은 양의 APPROACH 만큼만 채웁니다 -> 넘치지 않게 접근
//   · 배운 값이 없으면 DOSE_SEED 로 시작합니다
const float APPROACH   = 1.00f;     // 남은 양만큼 채우기 (배운 값이 맞으면 한 번에 도달)
const float LEARN_RATE = 0.35f;     // 학습 반영률 (EMA)
const int   DOSE_MIN   = 300;       // 너무 짧으면 펌프가 물을 못 밀어냅니다
const int   DOSE_MAX   = 2000;      // 20mL — 700mL 화분에 한 번에 줄 수 있는 상한

// 실측 유량 (PRIME 10초에 100mL) — 화면에 mL 로 보여 주기 위한 값입니다.
// 제어에는 쓰지 않습니다. 펌프나 튜브를 바꾸면 다시 재서 고치세요.
const float ML_PER_SEC = 10.0f;

// ── 침투 시간 측정 모드 ────────────────────────────────
// 1 로 두고 한 사이클만 돌리면, 도즈 뒤 raw 가 <언제 평탄해지는지> 알 수 있습니다.
// 그 시각이 SETTLE_MS 의 근거입니다. 튜브·센서 배치를 바꿀 때마다 다시 재세요.
//   측정이 끝나면 반드시 0 으로 되돌리세요.
#define SOAK_TEST  0

#if SOAK_TEST
  const unsigned long SETTLE_MS  = 1800000UL;  // 30분 — 끝까지 지켜봅니다
  const unsigned long SOAK_LOG_MS = 10000UL;   // 10초마다 raw 출력
#else
  const unsigned long SETTLE_MS  = 180000UL;   // 3분 — 물이 센서까지 퍼지는 시간
#endif
const int            MAX_SHOTS   = 6;          // 한 사이클 도즈 상한 -> 넘으면 이상
const int            MIN_DROP    = 3;          // 1도즈당 최소 raw 하강(카운트)
const int            NO_RISE_MAX = 2;          // 연속 몇 번 안 오르면 고장으로 볼 것인가
const unsigned long PUMP_HARD_MS = 5000UL;     // 어떤 경우에도 연속 ON 금지 한계
const unsigned long COOLDOWN_MS  = 600000UL;   // 이상 판정 후 재시도 금지(10분)
const int            PIN_PUMP    = 9;
const int            PIN_SOIL    = 8;

// ══════════════ 상태 ══════════════
enum State { S_SAFE, S_IDLE, S_DOSING, S_SETTLE, S_FAULT };
State st = S_SAFE;                      // 부팅 직후엔 절대 급수하지 않습니다

int   rawSoil = 0, rawBefore = 0, rawCycleStart = 0;
int   shots = 0;
int   doseMs = 0;                   // 이번에 실제로 튼 시간
int   noRise = 0;                   // 연속으로 "안 올랐다" 가 나온 횟수
float kPerMs = 0.0f;                // 학습값: 1ms 당 내려가는 counts
bool pumpOn = false;
unsigned long tPump = 0, tSettle = 0, tSoakLog = 0, tFault = 0, tDraw = 0;
const char* faultMsg = "";
bool primeLatch = false;


// ── 버튼 영역 (rotation 1 = 320x240) ──
const int AX=8,  AY=178, AW=150, AH=54;         // ARM / STOP
const int BX=162,BY=178, BW=150, BH=54;         // PRIME (누르는 동안 펌프)

// ══════════════ 변환 ══════════════
float pctOf(int raw){
  float v = 100.0f * (RAW_DRY - raw) / (float)(RAW_DRY - RAW_WET);
  return v < 0 ? 0 : (v > 100 ? 100 : v);
}
int rawOf(float pct){
  return (int)lroundf(RAW_DRY - pct / 100.0f * (RAW_DRY - RAW_WET));
}

// ══════════════ 센서 ══════════════
// 펌프가 도는 동안은 읽지 않습니다. 인러시로 전원이 처지면 값이 흔들립니다.
int readSoil(){
  if (pumpOn) return rawSoil;
  long acc = 0;
  for (int i = 0; i < 16; i++){ acc += analogRead(PIN_SOIL); delay(2); }
  return (int)(acc / 16);
}

// ══════════════ 펌프 ══════════════
int planDose(int raw){
  int need = raw - RAW_OFF;                       // 목표까지 남은 counts
  if (need <= 0) return 0;
  if (kPerMs <= 0.0f) return DOSE_SEED;           // 아직 배운 게 없으면 씨앗값

  long ms = (long)(need * APPROACH / kPerMs);
  // ★ 남은 양이 <최소 도즈보다 작으면> 주지 않고 멈춥니다.
  //   조금 마른 채로 두는 것이, 넘겨서 젖히는 것보다 낫습니다 —
  //   초과는 평균을 올려 두 처리군의 <평균 일치>를 깨뜨립니다.
  if (ms < DOSE_MIN) return 0;
  if (ms > DOSE_MAX) ms = DOSE_MAX;
  return (int)ms;
}

void learn(int drop, int ms){
  if (drop <= 0 || ms <= 0) return;               // 안 내려갔으면 배우지 않습니다
  float k = (float)drop / (float)ms;
  kPerMs = (kPerMs <= 0.0f) ? k : (1 - LEARN_RATE) * kPerMs + LEARN_RATE * k;
}

void setPump(bool on){
  if (on == pumpOn) return;
  pumpOn = on;
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
  if (on) tPump = millis();
}

#if USE_MQTT
WiFiClient   wifiCli;
PubSubClient mqtt(wifiCli);
unsigned long tSoilPub = 0, tRetry = 0;

struct Ev { char reason[14]; int before, after, dur, shots; };
Ev  evq[QUEUE_MAX];
int evHead = 0, evCount = 0;

void enqueue(const char* reason, int before, int after, int dur){
  int i = (evHead + evCount) % QUEUE_MAX;
  if (evCount == QUEUE_MAX){ evHead = (evHead + 1) % QUEUE_MAX; evCount--; }  // 오래된 것부터 버림
  strncpy(evq[i].reason, reason, sizeof(evq[i].reason) - 1);
  evq[i].reason[sizeof(evq[i].reason) - 1] = 0;
  evq[i].before = before; evq[i].after = after; evq[i].dur = dur; evq[i].shots = shots;
  evCount++;
}

bool netReady(){
  if (WiFi.status() != WL_CONNECTED) return false;
  if (mqtt.connected()) return true;
  unsigned long now = millis();
  if (now - tRetry < RETRY_MS) return false;      // ★ 절대 기다리지 않습니다
  tRetry = now;
  char cid[32]; snprintf(cid, sizeof(cid), "water-%s", NODE_ID);
  return mqtt.connect(cid);
}

void pubSoil(){
  char t[48], m[160];
  snprintf(t, sizeof(t), "plant/%s/soil", NODE_ID);
  snprintf(m, sizeof(m),
           "{\"node\":\"%s\",\"plant_id\":\"%s\",\"treat\":\"%s\","
           "\"pct\":%.1f,\"raw\":%d,\"n\":1}",
           NODE_ID, PLANT_ID, TREAT, pctOf(rawSoil), rawSoil);
  mqtt.publish(t, m);
}

void flushEvents(){
  while (evCount > 0){
    Ev& e = evq[evHead];
    char t[48], m[240];
    snprintf(t, sizeof(t), "plant/%s/pump", NODE_ID);
    snprintf(m, sizeof(m),
             "{\"node\":\"%s\",\"plant_id\":\"%s\",\"treat\":\"%s\",\"dur_ms\":%d,"
             "\"soil_before\":%.1f,\"soil_after\":%.1f,"
             "\"raw_before\":%d,\"raw_after\":%d,\"shots\":%d,\"reason\":\"%s\"}",
             NODE_ID, PLANT_ID, TREAT, e.dur, pctOf(e.before), pctOf(e.after),
             e.before, e.after, e.shots, e.reason);
    if (!mqtt.publish(t, m)) return;              // 실패하면 다음 기회에 다시
    evHead = (evHead + 1) % QUEUE_MAX; evCount--;
  }
}

void netLoop(){
  // 연결 상태가 <바뀔 때만> 한 줄 찍습니다. 붙었는지 안 붙었는지 알 수 있어야 합니다.
  static bool wasWifi = false, wasMqtt = false;
  bool nowWifi = (WiFi.status() == WL_CONNECTED);
  if (nowWifi != wasWifi){
    wasWifi = nowWifi;
    if (nowWifi) Serial.printf("[WIFI] 연결됨  %s\n", WiFi.localIP().toString().c_str());
    else         Serial.println("[WIFI] 끊김 — 급수는 계속됩니다");
  }
  bool nowMqtt = mqtt.connected();
  if (nowMqtt != wasMqtt){
    wasMqtt = nowMqtt;
    Serial.printf("[MQTT] %s  %s:%d\n", nowMqtt ? "연결됨" : "끊김", BROKER, BROKER_PORT);
  }

  if (!netReady()) return;
  mqtt.loop();
  flushEvents();                                  // 밀린 이벤트부터
  unsigned long now = millis();
  if (now - tSoilPub >= SOIL_PUB_MS){ tSoilPub = now; pubSoil(); }
}
#endif


void logEvent(const char* reason, int before, int after, int dur){
  // 필드 이름을 MQTT payload 와 같게 맞춰 둡니다 — 나중에 그대로 발행하면 됩니다.
  Serial.printf("{\"plant_id\":\"%s\",\"treat\":\"%s\",\"dur_ms\":%d,"
                "\"soil_before\":%.1f,\"soil_after\":%.1f,"
                "\"raw_before\":%d,\"raw_after\":%d,\"shots\":%d,\"reason\":\"%s\"}\n",
                PLANT_ID, TREAT, dur, pctOf(before), pctOf(after),
                before, after, shots, reason);
#if USE_MQTT
  enqueue(reason, before, after, dur);      // ★ 먼저 담고, 발행은 되는 대로
#endif
}

void toFault(const char* msg){
  setPump(false);
  st = S_FAULT; tFault = millis(); faultMsg = msg;
  logEvent(msg, rawCycleStart, rawSoil, 0);
}

// ══════════════ 화면 ══════════════
void drawUI(){
  M5.Display.startWrite();
  M5.Display.fillRect(0, 0, 320, 174, BLACK);

  M5.Display.setTextSize(2); M5.Display.setTextColor(TREAT[0]=='f' ? ORANGE : CYAN, BLACK);
  M5.Display.setCursor(10, 8);   M5.Display.printf("%s  %s", PLANT_ID, TREAT);

  M5.Display.setTextSize(3); M5.Display.setTextColor(WHITE, BLACK);
  M5.Display.setCursor(10, 34);  M5.Display.printf("%5.1f %%", pctOf(rawSoil));
  M5.Display.setTextSize(2); M5.Display.setTextColor(DARKGREY, BLACK);
  M5.Display.setCursor(190, 44); M5.Display.printf("raw %4d", rawSoil);

  M5.Display.setTextColor(DARKGREY, BLACK);
  M5.Display.setCursor(10, 74);
  M5.Display.printf("band %.0f-%.0f%% (raw %d..%d)",
                    pctOf(RAW_ON), pctOf(RAW_OFF), RAW_ON, RAW_OFF);

  const char* sn = "?";
  uint16_t sc = WHITE;
  switch (st){
    case S_SAFE:   sn = "SAFE (not armed)"; sc = DARKGREY; break;
    case S_IDLE:   sn = "watching";         sc = GREEN;    break;
    case S_DOSING: sn = "DOSING";           sc = RED;      break;
    case S_SETTLE: sn = "settling";         sc = YELLOW;   break;
    case S_FAULT:  sn = faultMsg;           sc = RED;      break;
  }
  M5.Display.setTextColor(sc, BLACK);
  M5.Display.setCursor(10, 100); M5.Display.printf("%-18s", sn);

  M5.Display.setTextColor(DARKGREY, BLACK);
  M5.Display.setCursor(10, 126);
  if (st == S_SETTLE){
    long left = (long)(SETTLE_MS - (millis() - tSettle)) / 1000;
    if (left < 0) left = 0;
    M5.Display.printf("wait %3lds  shot %d/%d", left, shots, MAX_SHOTS);
  } else if (st == S_FAULT){
    long left = (long)(COOLDOWN_MS - (millis() - tFault)) / 1000;
    if (left < 0) left = 0;
    M5.Display.printf("cooldown %3lds     ", left);
  } else {
    M5.Display.printf("shot %d/%d  %dms=%.1fmL  k%.2f",
                      shots, MAX_SHOTS, doseMs, doseMs / 1000.0f * ML_PER_SEC, kPerMs);
  }

  M5.Display.fillRoundRect(AX, AY, AW, AH, 8, st == S_SAFE ? NAVY : DARKGREEN);
  M5.Display.fillRoundRect(BX, BY, BW, BH, 8, pumpOn ? RED : 0x2104);
  M5.Display.setTextSize(2); M5.Display.setTextColor(WHITE);
  M5.Display.setCursor(AX + 34, AY + 18); M5.Display.print(st == S_SAFE ? "ARM " : "STOP");
  M5.Display.setCursor(BX + 26, BY + 18); M5.Display.print("PRIME");
  M5.Display.endWrite();
}

// ══════════════ setup ══════════════
void setup(){
#if USE_MQTT
  WiFi.mode(WIFI_STA);
  Serial.printf("[WIFI] ssid=[%s] pass_len=%d  broker=%s:%d\n",
                WIFI_SSID, (int)strlen(WIFI_PASS), BROKER, BROKER_PORT);
  WiFi.begin(WIFI_SSID, WIFI_PASS);         // ★ 연결될 때까지 기다리지 않습니다.
  WiFi.setAutoReconnect(true);              //   물 주는 일이 네트워크를 기다리면 안 됩니다.
  mqtt.setServer(BROKER, BROKER_PORT);
  mqtt.setKeepAlive(60);
#endif
  auto cfg = M5.config(); M5.begin(cfg);
  Serial.begin(115200);
  pinMode(PIN_PUMP, OUTPUT); digitalWrite(PIN_PUMP, LOW);   // 반드시 LOW 부터
  pinMode(PIN_SOIL, INPUT);  analogReadResolution(12);
  M5.Display.setRotation(1);
  M5.Display.fillScreen(BLACK);

  rawSoil = readSoil();

  Serial.printf("\n[BOOT] %s %s  raw %d..%d (gap %d) · center %d = %.1f%%\n",
                PLANT_ID, TREAT, RAW_ON, RAW_OFF, RAW_ON - RAW_OFF,
                BAND_CENTER, pctOf(BAND_CENTER));
  Serial.printf("[BOOT] 지금 흙: raw %d = %.1f%%\n", rawSoil, pctOf(rawSoil));
  Serial.printf("[BOOT] 첫 도즈 %d ms (%.1f mL) · 대기 %lu s · 최대 %d회 · 도즈 %d~%d ms\n",
                DOSE_SEED, DOSE_SEED / 1000.0f * ML_PER_SEC,
                SETTLE_MS / 1000, MAX_SHOTS, DOSE_MIN, DOSE_MAX);
  if (RAW_ON - RAW_OFF < 20)
    Serial.println("[WARN] 밴드가 raw 20카운트 미만입니다 — 노이즈와 구분이 어렵습니다");
  Serial.println("[BOOT] SAFE 상태. 초기 젖음을 끝낸 뒤 ARM 을 누르세요.");
  drawUI();
}

// ══════════════ loop ══════════════
void loop(){
#if USE_MQTT
  netLoop();                                // 연결·발행 — 어떤 경우에도 블로킹하지 않습니다
#endif
  M5.update();
  unsigned long now = millis();

  // ── 하드 상한: 무슨 상태든 이 시간을 넘겨 켜져 있으면 강제 OFF ──
  if (pumpOn && now - tPump > PUMP_HARD_MS){
    setPump(false); primeLatch = true;
    Serial.println("[SAFETY] hard limit");
    if (st == S_DOSING){ st = S_SETTLE; tSettle = now; tSoakLog = now; }
  }

  // ── 터치 ──
  auto t = M5.Touch.getDetail();
  bool inA = t.isPressed() && t.x>=AX && t.x<=AX+AW && t.y>=AY && t.y<=AY+AH;
  bool inB = t.isPressed() && t.x>=BX && t.x<=BX+BW && t.y>=BY && t.y<=BY+BH;

  if (t.wasPressed() && inA){
    if (st == S_SAFE){ st = S_IDLE; shots = 0; Serial.println("[ARM] 폐루프 시작"); }
    else { setPump(false); st = S_SAFE; Serial.println("[STOP] SAFE 로 복귀"); }
  }

  // PRIME — 누르는 동안만. 손을 떼야 다시 켜집니다(하드 상한 무력화 방지).
  if (st == S_SAFE || st == S_FAULT){
    if (inB && !pumpOn && !primeLatch) setPump(true);
    if (!inB){ if (pumpOn) setPump(false); primeLatch = false; }
  }

  // ── 상태기계 ──
  switch (st){

    case S_IDLE:
      rawSoil = readSoil();
      if (rawSoil >= RAW_ON){                 // raw 가 크다 = 말랐다
        rawCycleStart = rawSoil; shots = 0;
        rawBefore = rawSoil; doseMs = planDose(rawSoil);
        if (doseMs > 0){ setPump(true); st = S_DOSING; }
      }
      break;

    case S_DOSING:
      if (now - tPump >= (unsigned long)doseMs){
        setPump(false); shots++;
        st = S_SETTLE; tSettle = now; tSoakLog = now;
      }
      break;

    case S_SETTLE:
#if SOAK_TEST
      if (now - tSoakLog >= SOAK_LOG_MS){       // 침투 곡선을 그대로 찍습니다
        tSoakLog = now;
        Serial.printf("[SOAK] %5lus  raw %4d  (도즈 후 하강 %d)\n",
                      (now - tSettle) / 1000, rawSoil, rawBefore - rawSoil);
      }
#endif
      if (now - tSettle >= SETTLE_MS){
        rawSoil = readSoil();
        int drop = rawBefore - rawSoil;        // 젖으면 raw 가 내려갑니다
        learn(drop, doseMs);                   // ★ 다음 도즈 길이에 반영
        logEvent("dosed", rawBefore, rawSoil, doseMs);

        if (drop >= MIN_DROP) noRise = 0;      // 한 번이라도 올랐으면 초기화

        if (rawSoil <= RAW_OFF){               // 목표 도달
          logEvent("filled", rawCycleStart, rawSoil, doseMs);
          shots = 0; noRise = 0; st = S_IDLE;
        } else if (drop < MIN_DROP && ++noRise >= NO_RISE_MAX){
          // ★ 한 번으로 단정하지 않습니다.
          //   마른 흙은 첫 도즈가 통째로 빠져나가 센서까지 안 옵니다 —
          //   진짜 고장(튜브 빠짐·물통 빔)이면 <연속으로> 안 오릅니다.
          toFault("no rise");                  // 물통·튜브 확인
        } else if (shots >= MAX_SHOTS){        // 너무 여러 번
          toFault("verify fail");
        } else {
          rawBefore = rawSoil; doseMs = planDose(rawSoil);
          if (doseMs > 0){ setPump(true); st = S_DOSING; }
          else {                                 // 한 방울이면 넘칩니다 — 여기서 끝
            logEvent("filled", rawCycleStart, rawSoil, 0);
            shots = 0; st = S_IDLE;
          }
        }
      }
      break;

    case S_FAULT:
      if (now - tFault >= COOLDOWN_MS){        // 쿨다운 뒤 한 번 더 기회
        shots = 0; noRise = 0; st = S_IDLE;
        Serial.println("[FAULT] cooldown 종료 — 재시도");
      }
      break;

    case S_SAFE:
      rawSoil = readSoil();
      break;
  }

  if (now - tDraw > 250){ drawUI(); tDraw = now; }
}
