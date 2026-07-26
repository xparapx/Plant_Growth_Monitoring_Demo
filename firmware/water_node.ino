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

// ══════════════ 노드 설정 — 여기만 고칩니다 ══════════════
#define TREAT_FLUCT   0                 // 0 = 꾸준군(stable) · 1 = 널뜀군(fluct)
const char* PLANT_ID = "p1";            // 화분 이름 (p1, p2, ...)

// 센서 보정 — 2026-07 실측 (공기 2133 / 포장용수량 1750)
//   ★ raw 는 젖으면 내려갑니다.  마른 흙으로 DRY 를 다시 잡으면 이 두 줄만 고치세요.
const int RAW_DRY = 2133;
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
  const int   DOSE_MS = 2000;           // 폭이 커서 편류가 쉬움 -> 잘게 여러 번
#else
  const char* TREAT   = "stable";
  const int   RAW_ON  = 1940;
  const int   RAW_OFF = 1900;
  const int   DOSE_MS = 1200;           // 밴드가 좁아 한 번에 넘기기 쉬움
#endif
const int BAND_CENTER = (RAW_ON + RAW_OFF) / 2;   // 두 노드가 같은지 부팅 로그로 확인

// ══════════════ 안전·타이밍 ══════════════
const unsigned long SETTLE_MS    = 180000UL;   // 3분  — 물이 센서까지 퍼지는 시간
const int            MAX_SHOTS   = 6;          // 한 사이클 도즈 상한 -> 넘으면 이상
const int            MIN_DROP    = 3;          // 1도즈당 최소 raw 하강(카운트)
const unsigned long PUMP_HARD_MS = 5000UL;     // 어떤 경우에도 연속 ON 금지 한계
const unsigned long COOLDOWN_MS  = 600000UL;   // 이상 판정 후 재시도 금지(10분)
const int            PIN_PUMP    = 9;
const int            PIN_SOIL    = 8;

// ══════════════ 상태 ══════════════
enum State { S_SAFE, S_IDLE, S_DOSING, S_SETTLE, S_FAULT };
State st = S_SAFE;                      // 부팅 직후엔 절대 급수하지 않습니다

int  rawSoil = 0, rawBefore = 0, rawCycleStart = 0;
int  shots = 0;
bool pumpOn = false;
unsigned long tPump = 0, tSettle = 0, tFault = 0, tDraw = 0;
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
void setPump(bool on){
  if (on == pumpOn) return;
  pumpOn = on;
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
  if (on) tPump = millis();
}

void logEvent(const char* reason, int before, int after, int dur){
  // 필드 이름을 MQTT payload 와 같게 맞춰 둡니다 — 나중에 그대로 발행하면 됩니다.
  Serial.printf("{\"plant_id\":\"%s\",\"treat\":\"%s\",\"dur_ms\":%d,"
                "\"soil_before\":%.1f,\"soil_after\":%.1f,"
                "\"raw_before\":%d,\"raw_after\":%d,\"shots\":%d,\"reason\":\"%s\"}\n",
                PLANT_ID, TREAT, dur, pctOf(before), pctOf(after),
                before, after, shots, reason);
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
    M5.Display.printf("shot %d/%d          ", shots, MAX_SHOTS);
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
  Serial.printf("[BOOT] dose %d ms · settle %lu s · max %d shots\n",
                DOSE_MS, SETTLE_MS / 1000, MAX_SHOTS);
  if (RAW_ON - RAW_OFF < 20)
    Serial.println("[WARN] 밴드가 raw 20카운트 미만입니다 — 노이즈와 구분이 어렵습니다");
  Serial.println("[BOOT] SAFE 상태. 초기 젖음을 끝낸 뒤 ARM 을 누르세요.");
  drawUI();
}

// ══════════════ loop ══════════════
void loop(){
  M5.update();
  unsigned long now = millis();

  // ── 하드 상한: 무슨 상태든 이 시간을 넘겨 켜져 있으면 강제 OFF ──
  if (pumpOn && now - tPump > PUMP_HARD_MS){
    setPump(false); primeLatch = true;
    Serial.println("[SAFETY] hard limit");
    if (st == S_DOSING){ st = S_SETTLE; tSettle = now; }
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
        rawBefore = rawSoil; setPump(true); st = S_DOSING;
      }
      break;

    case S_DOSING:
      if (now - tPump >= (unsigned long)DOSE_MS){
        setPump(false); shots++;
        st = S_SETTLE; tSettle = now;
      }
      break;

    case S_SETTLE:
      if (now - tSettle >= SETTLE_MS){
        rawSoil = readSoil();
        int drop = rawBefore - rawSoil;        // 젖으면 raw 가 내려갑니다
        logEvent("dosed", rawBefore, rawSoil, DOSE_MS);

        if (rawSoil <= RAW_OFF){               // 목표 도달
          logEvent("filled", rawCycleStart, rawSoil, DOSE_MS * shots);
          shots = 0; st = S_IDLE;
        } else if (drop < MIN_DROP){           // 물이 안 들어온다
          toFault("no rise");                  // 물통·튜브 확인
        } else if (shots >= MAX_SHOTS){        // 너무 여러 번
          toFault("verify fail");
        } else {
          rawBefore = rawSoil; setPump(true); st = S_DOSING;
        }
      }
      break;

    case S_FAULT:
      if (now - tFault >= COOLDOWN_MS){        // 쿨다운 뒤 한 번 더 기회
        shots = 0; st = S_IDLE; Serial.println("[FAULT] cooldown 종료 — 재시도");
      }
      break;

    case S_SAFE:
      rawSoil = readSoil();
      break;
  }

  if (now - tDraw > 250){ drawUI(); tDraw = now; }
}
