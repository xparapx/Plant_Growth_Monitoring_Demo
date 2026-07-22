#include <M5Unified.h>
const int PIN_PUMP = 9;                 // 노랑 PUMP_EN (실측)
const int PIN_SOIL = 8;                 // 흰색 Analog  (실측)
const unsigned long MAX_ON_MS = 5000;   // 안전: 5초 넘으면 강제 OFF
const int SOIL_DRY = 3200, SOIL_WET = 1400;      // ★ 임시 — 보정값으로 교체
const int BX=40, BY=150, BW=240, BH=70;          // 버튼 영역

bool pumpOn=false; unsigned long pumpStart=0; int rawSoil=0;

float soilPct(int r){ float v=100.0f*(SOIL_DRY-r)/(float)(SOIL_DRY-SOIL_WET);
                      return v<0?0:(v>100?100:v); }

void setPump(bool on){
  if(on==pumpOn) return;
  pumpOn=on; digitalWrite(PIN_PUMP, on?HIGH:LOW);
  if(on) pumpStart=millis();
  Serial.printf("[PUMP] %s  raw=%d  %.1f%%\n", on?"ON":"OFF", rawSoil, soilPct(rawSoil));
}
void drawUI(){
  M5.Display.fillScreen(BLACK);
  M5.Display.setTextColor(WHITE,BLACK); M5.Display.setTextSize(2);
  M5.Display.setCursor(10,10);  M5.Display.printf("Soil raw : %4d", rawSoil);
  M5.Display.setTextSize(3); M5.Display.setTextColor(CYAN,BLACK);
  M5.Display.setCursor(10,40);  M5.Display.printf("%.1f %%", soilPct(rawSoil));
  M5.Display.setTextSize(2); M5.Display.setTextColor(pumpOn?RED:DARKGREY,BLACK);
  M5.Display.setCursor(10,90);  M5.Display.printf("PUMP : %s", pumpOn?"ON ":"off");
  M5.Display.fillRoundRect(BX,BY,BW,BH,10, pumpOn?RED:NAVY);
  M5.Display.setTextColor(WHITE); M5.Display.setTextSize(3);
  M5.Display.setCursor(BX+55,BY+22); M5.Display.print("PUMP");
}
void setup(){
  auto cfg=M5.config(); M5.begin(cfg); Serial.begin(115200);
  pinMode(PIN_PUMP,OUTPUT); digitalWrite(PIN_PUMP,LOW);   // LOW부터
  pinMode(PIN_SOIL,INPUT);  analogReadResolution(12);
  M5.Display.setRotation(1); drawUI();
}
void loop(){
  M5.update();
  long acc=0; for(int i=0;i<8;i++){ acc+=analogRead(PIN_SOIL); delay(2); }
  rawSoil=acc/8;

  auto t=M5.Touch.getDetail();
  bool onBtn = t.isPressed() && t.x>=BX && t.x<=BX+BW && t.y>=BY && t.y<=BY+BH;
  if(onBtn && !pumpOn) setPump(true);
  if(!onBtn && pumpOn) setPump(false);

  if(pumpOn && millis()-pumpStart>MAX_ON_MS){ Serial.println("[SAFETY] OFF"); setPump(false); }
  drawUI(); delay(50);
}
