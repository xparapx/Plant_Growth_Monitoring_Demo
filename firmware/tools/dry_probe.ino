/*
  dry_probe.ino — 널뜀군(fluct) 마름 구간 1회 측정   [firmware/tools/]
  M5Stack CoreS3 + Watering Unit U101 (SOIL=G8)      펌프·WiFi·MQTT·DB 없음

  ■ 재는 것 (raw 는 마를수록 커진다)
      수분 90%→20% 를 10% 씩 내려가는 데 걸린 시간(h)과 통과 순간 raw 를 기록한다.
      → 구간별 마름 속도 7개.  밴드 range 를 고를 때 이 표를 쓴다.
      ★ % 는 RAW_DRY/RAW_WET 보정에 종속된다. range 는 반드시 표의 raw 열로 옮겨 적을 것.
      채움·회복 구간은 재지 않으므로 어떤 구간 시간도 '주기'가 아니라 그 하한이다.
  ■ 시작 조건: 손 급수로 raw < 1788(90%) 인 상태에서 켠다.
      더 마른 상태에서 켜면 이미 지난 문턱은 '--' 로 남고 P(partial) 표시.
  ■ 참고선으로 현 밴드(1820/2020)를 차트에 그리고, 2020 도달 예상은 6h 기울기로 외삽('*').
  ■ 출력: 화면 / Serial CSV(10분 1점) / SD /dry_probe.csv (카드 없으면 건너뜀)
  ■ 조작: 화면 하단 [START] 터치 = 시작(WAIT 에서만)  ·  [RESET] 2초 누르기 = 처음부터
      (베젤 아래 터치 띠의 BtnA/B/C 는 쓰지 않는다 — 화면에 안 보여서)
*/
#include <M5Unified.h>
#include <SD.h>

const int PIN_PUMP = 9, PIN_SOIL = 8;                  // 펌프 핀은 LOW 고정만
const int RAW_DRY = 2133, RAW_WET = 1750;              // % 표시 전용
const int RAW_ON  = 2020, RAW_OFF = 1820;              // = water_node.ino fluct 밴드
const unsigned long SAMPLE_MS = 10000UL, BIN_MS = 600000UL;   // 10초 샘플, 10분 평균
const int NBIN = 288;                                  // 차트 창 48시간
const int PCT_HI = 90, PCT_LO = 20, PCT_STEP = 10;     // 90,80,…,20 %
const int NSUB = (PCT_HI - PCT_LO) / PCT_STEP + 1;    // = 8 문턱
const int CONFIRM = 3, SLOPE_BINS = 36;                // 30초 연속 확인 / 회귀창 6h
const float WEEKS = 6.0f;
const char* CSV = "/dry_probe.csv";

enum State { S_WAIT, S_DRY, S_DONE };
const char* SN[] = {"WAIT", "DRYING", "DONE"};
State st = S_WAIT;

int raw = 0, nextSub = 0, confirmN = 0;
bool sdOK = false, partial = false;
unsigned long tSample = 0, tBin = 0, tSub[NSUB];      // 문턱 통과 시각(ms), 0 = 미통과
int   rawAt[NSUB];                                     // 통과 순간 raw (표에 그대로 씀)
float bins[NBIN]; int head = 0, nBins = 0; double binAcc = 0; int binN = 0;
M5Canvas cv(&M5.Display);
const int BTN_Y = 214, BTN_H = 26;                     // 하단 버튼 띠
const int BTN_START_X0 = 8, BTN_START_X1 = 156, BTN_RESET_X0 = 164, BTN_RESET_X1 = 312;
const unsigned long RESET_HOLD_MS = 2000;
unsigned long tHold = 0; bool holding = false;         // RESET 길게 누르기 진행

float hours(unsigned long ms) { return ms / 3600000.0f; }
float pct(int r) { float p = (RAW_DRY - r) * 100.0f / (RAW_DRY - RAW_WET); return constrain(p, 0, 100); }
int subPct(int k) { return PCT_HI - k * PCT_STEP; }                              // 90,80,…
int subThr(int k) { return RAW_DRY - subPct(k) * (RAW_DRY - RAW_WET) / 100; }    // %→raw, 마를수록 큼

int readSoil() { long a = 0; for (int i = 0; i < 16; i++) { a += analogRead(PIN_SOIL); delay(2); } return a / 16; }
void logLine(const String& s) {
  Serial.println(s);
  if (!sdOK) return;
  File f = SD.open(CSV, FILE_APPEND); if (f) { f.println(s); f.close(); }
}
void logEvent(const char* w) { logLine(String("#") + millis() + "," + w + ",raw=" + raw + ",sub=" + nextSub); }

float slopePerHour() {                                 // 최근 6h 최소제곱 기울기, counts/h
  int n = min(nBins, SLOPE_BINS); if (n < 6) return 0;
  double sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (int i = 0; i < n; i++) { float y = bins[(head - n + i + NBIN) % NBIN]; sx += i; sy += y; sxx += (double)i * i; sxy += (double)i * y; }
  return (float)((n * sxy - sx * sy) / (n * sxx - sx * sx) * 3600000.0 / BIN_MS);
}

void startProbe() {
  memset(tSub, 0, sizeof(tSub));
  nextSub = 0; while (nextSub < NSUB && raw >= subThr(nextSub)) nextSub++;    // 이미 지난 문턱은 건너뜀
  partial = nextSub > 0;
  if (nextSub >= NSUB) { st = S_DONE; logEvent("ALREADY_DRY"); return; }
  confirmN = 0; st = S_DRY; logEvent(partial ? "START_PARTIAL" : "START");
}
void resetAll() { st = S_WAIT; nBins = 0; head = 0; binAcc = 0; binN = 0; logEvent("RESET"); }

void onSample(unsigned long now) {
  if (st != S_DRY) return;
  if (raw >= subThr(nextSub)) confirmN++; else confirmN = 0;
  if (confirmN < CONFIRM) return;
  confirmN = 0; tSub[nextSub] = now; rawAt[nextSub] = raw;
  float dh = (nextSub > 0 && tSub[nextSub - 1]) ? hours(now - tSub[nextSub - 1]) : -1;   // 직전 문턱부터 걸린 시간
  logLine(String("#CROSS,pct=") + subPct(nextSub) + ",raw=" + raw + ",dh=" + (dh < 0 ? String("start") : String(dh, 2)) + ",h=" + String(hours(now), 2));
  if (++nextSub >= NSUB) {
    st = S_DONE;
    String s = "#DONE";                                  // pct:raw:dh 를 한 줄로
    for (int k = 0; k < NSUB; k++) {
      bool ok = tSub[k] && k > 0 && tSub[k - 1];
      s += "," + String(subPct(k)) + ":" + (tSub[k] ? String(rawAt[k]) : String("--")) + ":" + (ok ? String(hours(tSub[k] - tSub[k - 1]), 2) : String("--"));
    }
    logLine(s);
  }
}

void draw(unsigned long now) {
  cv.fillSprite(TFT_BLACK);
  uint16_t sc = st == S_DRY ? TFT_GREEN : st == S_DONE ? TFT_CYAN : TFT_DARKGREY;
  cv.setTextDatum(top_left); cv.setTextColor(TFT_WHITE);
  cv.setFont(&fonts::Font7); cv.drawNumber(raw, 6, 4);
  cv.setFont(&fonts::Font2);
  cv.drawString(String(pct(raw), 1) + " %", 150, 6);
  cv.setTextColor(sc); cv.drawString(String(SN[st]) + (partial ? " P" : ""), 215, 6);
  cv.setTextColor(TFT_WHITE);
  cv.drawString(st == S_WAIT ? "wet to <" + String(subThr(0)) + ", L=start"
              : st == S_DRY ? "next " + String(subPct(nextSub)) + "% = " + String(subThr(nextSub))
              : String("finished"), 150, 26);
  cv.drawString("run " + String(hours(now), 1) + "h  SD " + (sdOK ? "ok" : "--"), 150, 44);

  const int X0 = 8, X1 = 312, Y0 = 62, Y1 = 118; const float V0 = 1750, V1 = 2080;
  auto yOf = [&](float v) { return constrain((int)(Y1 - (v - V0) * (Y1 - Y0) / (V1 - V0)), Y0, Y1); };
  const float px = (float)(X1 - X0) / NBIN;
  cv.drawRect(X0 - 1, Y0 - 1, X1 - X0 + 2, Y1 - Y0 + 2, TFT_DARKGREY);
  for (int x = X0; x < X1; x += 6) { cv.drawPixel(x, yOf(RAW_OFF), TFT_CYAN); cv.drawPixel(x, yOf(RAW_ON), TFT_ORANGE); }
  cv.setTextColor(TFT_CYAN);   cv.drawString(String(RAW_OFF), X1 - 30, yOf(RAW_OFF) - 14);
  cv.setTextColor(TFT_ORANGE); cv.drawString(String(RAW_ON),  X1 - 30, yOf(RAW_ON) + 2);
  for (int k = 0; k < NSUB; k++) if (tSub[k])                                     // 통과점 표시
    cv.fillCircle(X1 - 2 - (int)((now - tSub[k]) / BIN_MS * px), yOf(rawAt[k]), 2, TFT_YELLOW);
  int lx = -1, ly = -1;
  for (int i = 0; i < nBins; i++) {
    int x = X0 + (int)((NBIN - nBins + i) * px), y = yOf(bins[(head - nBins + i + NBIN) % NBIN]);
    if (lx >= 0) cv.drawLine(lx, ly, x, y, TFT_WHITE); else cv.drawPixel(x, y, TFT_WHITE);
    lx = x; ly = y;
  }
  cv.fillCircle(X1 - 2, yOf(raw), 2, TFT_GREEN);

  // 표: pct  raw  10%당 소요 h   (2열 × 4행)   — 값은 "직전 문턱 → 이 문턱" 시간
  for (int k = 0; k < NSUB; k++) {
    int col = k / 4, row = k % 4, x = 8 + col * 160, y = 124 + row * 17;
    bool done = tSub[k] != 0, cur = st == S_DRY && k == nextSub, hasPrev = k > 0 && tSub[k - 1];
    cv.setTextColor(done ? TFT_WHITE : cur ? TFT_GREEN : TFT_DARKGREY);
    String t = done ? (hasPrev ? String(hours(tSub[k] - tSub[k - 1]), 1) + "h" : String("start"))
             : cur  ? (hasPrev ? String(hours(now - tSub[k - 1]), 1) + "h.." : String("..."))
             :        String("--");
    cv.drawString(String(subPct(k)) + "% " + String(done ? rawAt[k] : subThr(k)) + "  " + t, x, y);
  }
  float rate = slopePerHour();
  String foot = "slope " + String(rate, 1) + " ct/h";
  if (st == S_DRY && rate > 0.5f && raw < RAW_ON) foot += "  ->2020 in " + String((RAW_ON - raw) / rate, 1) + "h*";
  cv.setTextColor(TFT_YELLOW); cv.drawString(foot, 8, 194);

  // 하단 버튼 두 개
  cv.setTextDatum(middle_center);
  bool canStart = st == S_WAIT;
  cv.fillRoundRect(BTN_START_X0, BTN_Y, BTN_START_X1 - BTN_START_X0, BTN_H, 5, canStart ? TFT_DARKGREEN : TFT_DARKGREY);
  cv.setTextColor(canStart ? TFT_WHITE : TFT_BLACK);
  cv.drawString(canStart ? "START" : SN[st], (BTN_START_X0 + BTN_START_X1) / 2, BTN_Y + BTN_H / 2);
  cv.fillRoundRect(BTN_RESET_X0, BTN_Y, BTN_RESET_X1 - BTN_RESET_X0, BTN_H, 5, TFT_MAROON);
  if (holding) {                                       // 누른 시간만큼 채워짐
    int w = (int)((BTN_RESET_X1 - BTN_RESET_X0) * min(1.0f, (now - tHold) / (float)RESET_HOLD_MS));
    cv.fillRoundRect(BTN_RESET_X0, BTN_Y, w, BTN_H, 5, TFT_RED);
  }
  cv.setTextColor(TFT_WHITE);
  cv.drawString(holding ? "hold..." : "RESET (hold 2s)", (BTN_RESET_X0 + BTN_RESET_X1) / 2, BTN_Y + BTN_H / 2);
  cv.setTextDatum(top_left);
  cv.pushSprite(0, 0);
}

void setup() {
  pinMode(PIN_PUMP, OUTPUT); digitalWrite(PIN_PUMP, LOW);   // 유닛이 꽂혀 있으므로 LOW 고정
  auto cfg = M5.config(); M5.begin(cfg); Serial.begin(115200);
  pinMode(PIN_SOIL, INPUT); analogReadResolution(12);
  cv.setPsram(true); cv.setColorDepth(16); cv.createSprite(320, 240);
  sdOK = SD.begin(GPIO_NUM_4, SPI, 25000000);
  memset(tSub, 0, sizeof(tSub));
  raw = readSoil();
  Serial.printf("# dry_probe DRY=%d WET=%d  grid %d..%d%% step %d  (band ref ON=%d OFF=%d)\n", RAW_DRY, RAW_WET, PCT_HI, PCT_LO, PCT_STEP, RAW_ON, RAW_OFF);
  for (int k = 0; k < NSUB; k++) Serial.printf("#   %d%% = raw %d\n", subPct(k), subThr(k));
  logLine("ms,state,raw10min,pct,nextSub");
}

void loop() {
  M5.update();
  unsigned long now = millis();
  auto t = M5.Touch.getDetail();
  bool inStart = t.y >= BTN_Y && t.y < BTN_Y + BTN_H && t.x >= BTN_START_X0 && t.x < BTN_START_X1;
  bool inReset = t.y >= BTN_Y && t.y < BTN_Y + BTN_H && t.x >= BTN_RESET_X0 && t.x < BTN_RESET_X1;
  if (t.wasClicked() && inStart && st == S_WAIT) startProbe();
  if (t.wasPressed() && inReset) { holding = true; tHold = now; }
  if (holding && (!t.isPressed() || !inReset)) holding = false;          // 손을 떼거나 벗어나면 취소
  if (holding && now - tHold >= RESET_HOLD_MS) { holding = false; resetAll(); }
  if (now - tSample >= SAMPLE_MS) { tSample = now; raw = readSoil(); binAcc += raw; binN++; onSample(now); }
  if (now - tBin >= BIN_MS) {
    tBin = now;
    if (binN) {
      bins[head] = binAcc / binN; head = (head + 1) % NBIN; if (nBins < NBIN) nBins++;
      logLine(String(now) + "," + SN[st] + "," + String(binAcc / binN, 1) + "," + String(pct(raw), 1) + "," + nextSub);
    }
    binAcc = 0; binN = 0;
  }
  static unsigned long tDraw = 0;
  if (now - tDraw >= (holding ? 100 : 1000)) { tDraw = now; draw(now); }   // 홀드 중엔 진행바 갱신
  delay(20);
}
