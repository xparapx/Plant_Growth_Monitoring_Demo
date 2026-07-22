#include <Wire.h>
#include <Adafruit_BME680.h>
#include <SensirionI2cScd4x.h>          // ★ 신버전: I2c 소문자
#include <BH1750.h>

#ifdef NO_ERROR
#undef NO_ERROR
#endif
#define NO_ERROR 0

const uint16_t ALTITUDE_M = 40;         // ★ 학교 해발고도(m)
const uint8_t  SCD41_ADDR = 0x62;

Adafruit_BME680   bme;
SensirionI2cScd4x scd4x;
BH1750            lightMeter;
bool bmeOK=false, scdOK=false, luxOK=false;

float esat(float t){ return 0.6108f*expf(17.27f*t/(t+237.3f)); }
float vpdOf(float t,float rh){ return esat(t)*(1.0f-rh/100.0f); }

void setup(){
  Serial.begin(115200);
  while(!Serial && millis()<3000){}
  Wire.begin();
  delay(200);

  bmeOK = bme.begin(0x76) || bme.begin(0x77);
  if(bmeOK){
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
    bme.setGasHeater(0,0);              // 가스히터 OFF
  }
  Serial.println(bmeOK?"BME688 OK":"BME688 FAIL");

  scd4x.begin(Wire, SCD41_ADDR);        // ★ 신버전: 주소 인자
  scd4x.stopPeriodicMeasurement(); delay(500);
  scd4x.setSensorAltitude(ALTITUDE_M);
  scdOK = (scd4x.startPeriodicMeasurement()==NO_ERROR);
  Serial.println(scdOK?"SCD41 OK (첫 값 ~5초)":"SCD41 FAIL");

  luxOK = lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  Serial.println(luxOK?"DLight OK":"DLight FAIL");
}

void loop(){
  float t=NAN,hm=NAN,pr=NAN,vpd=NAN,lx=NAN; uint16_t co2=0;

  if(bmeOK && bme.performReading()){
    t=bme.temperature; hm=bme.humidity; pr=bme.pressure/100.0f; vpd=vpdOf(t,hm);
  }
  bool ready=false;
  if(scdOK && scd4x.getDataReadyStatus(ready)==NO_ERROR && ready){   // ★ 신버전 함수명
    float st,sh; scd4x.readMeasurement(co2, st, sh);   // 온습도는 버림 (CO2만)
  }
  if(luxOK) lx=lightMeter.readLightLevel();

  Serial.print("T=");   if(!isnan(t))  Serial.print(t,1);  else Serial.print("--");
  Serial.print("C RH=");if(!isnan(hm)) Serial.print(hm,1); else Serial.print("--");
  Serial.print("% P="); if(!isnan(pr)) Serial.print(pr,1); else Serial.print("--");
  Serial.print("hPa VPD=");if(!isnan(vpd))Serial.print(vpd,2);else Serial.print("--");
  Serial.print("kPa CO2=");if(co2)      Serial.print(co2);  else Serial.print("--");
  Serial.print("ppm Lux=");if(!isnan(lx))Serial.print(lx,0);else Serial.print("--");
  Serial.println();
  delay(2000);
}
