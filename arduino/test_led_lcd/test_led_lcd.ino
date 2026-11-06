/*
 * Test : LED rouge allumée + « Hello World » sur le LCD I2C
 *
 * LED rouge : D10 (+ résistance 220 ohms, patte courte au GND)
 * LCD I2C   : SDA -> A4, SCL -> A5, VCC -> 5V, GND -> GND
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const int PIN_LED_ROUGE = 10;

LiquidCrystal_I2C* lcd = nullptr;

void setup() {
  Serial.begin(9600);

  // LED rouge allumée
  pinMode(PIN_LED_ROUGE, OUTPUT);
  digitalWrite(PIN_LED_ROUGE, HIGH);
  Serial.println("LED rouge allumee (D10)");

  // Recherche de l'écran sur le bus I2C
  Wire.begin();
  uint8_t adresse = 0;
  for (uint8_t adr = 0x08; adr < 0x78; adr++) {
    Wire.beginTransmission(adr);
    if (Wire.endTransmission() == 0) {
      adresse = adr;
      break;
    }
  }

  if (adresse == 0) {
    Serial.println("LCD introuvable : verifier SDA->A4, SCL->A5, VCC->5V, GND");
    return;
  }

  Serial.print("LCD trouve a l'adresse 0x");
  Serial.println(adresse, HEX);

  lcd = new LiquidCrystal_I2C(adresse, 16, 2);
  lcd->init();
  lcd->backlight();
  lcd->setCursor(0, 0);
  lcd->print("Hello World");
}

void loop() {
}
