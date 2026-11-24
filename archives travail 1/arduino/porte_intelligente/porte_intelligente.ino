#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>


// ===== BROCHES =====
const int PIN_BOUTON    = 2;   // D2  (l'autre patte au GND)
const int PIN_PIR       = 3;   // D3  (sortie OUT du PIR)
const int PIN_TRIG      = 4;   // D4  (TRIG du capteur ultrason HC-SR04)
const int PIN_ECHO      = 5;   // D5  (ECHO du capteur ultrason HC-SR04)
const int PIN_BUZZER    = 8;   // D8
const int PIN_SERVO     = 9;   // D9  (fil signal du servo)
const int PIN_LED_ROUGE = 10;  // D10 (+ résistance 220 ohms)
const int PIN_LED_VERTE = 11;  // D11 (+ résistance 220 ohms)
// LCD I2C : SDA -> A4, SCL -> A5, VCC -> 5V, GND -> GND


// ===== COMPOSANTS =====
Servo servoPorte;
LiquidCrystal_I2C* lcd = nullptr;   // créé au démarrage avec la bonne adresse


// Angles du servo (entre 0 et 180)
const int PORTE_FERMEE  = 0;
const int PORTE_OUVERTE = 90;


// Temps
const unsigned long DUREE_OUVERTURE = 3000;
const unsigned long ANTI_REBOND     = 40;
const unsigned long PERIODE_DISTANCE = 100;  // une mesure toutes les 100 ms


// Capteur de distance : la porte s'ouvre (ou reste ouverte) si quelqu'un est à moins de 15 cm
const int DISTANCE_OUVERTURE_CM = 15;


// Variables
bool porteOuverte = false;
bool mouvementDetecte = false;

int distanceCm = 999;
unsigned long derniereMesure = 0;


unsigned long tempsOuverture = 0;
unsigned long dernierChangementBouton = 0;


int dernierEtatBouton = HIGH;
int etatBoutonStable  = HIGH;


// Cherche l'écran LCD sur le bus I2C (0x27 ou 0x3F le plus souvent)
uint8_t trouverAdresseLCD() {
  for (uint8_t adr = 0x08; adr < 0x78; adr++) {
    Wire.beginTransmission(adr);
    if (Wire.endTransmission() == 0) return adr;
  }
  return 0;  // aucun écran trouvé
}


// Mesure la distance en cm avec le capteur ultrason (999 = rien devant)
int lireDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  unsigned long duree = pulseIn(PIN_ECHO, HIGH, 25000UL);  // ~4 m max
  if (duree == 0) return 999;
  return duree / 58;
}


// Affiche 2 lignes (max 16 caractères chacune) sur le LCD et le Moniteur série
void afficherEtat(const char* ligne1, const char* ligne2) {
  Serial.print(ligne1);
  Serial.print(" | ");
  Serial.println(ligne2);

  if (lcd == nullptr) return;  // pas d'écran : le programme continue quand même
  lcd->clear();
  lcd->setCursor(0, 0);
  lcd->print(ligne1);
  lcd->setCursor(0, 1);
  lcd->print(ligne2);
}


void ouvrirPorte() {
  if (porteOuverte) {
    // Prolonge le temps d'ouverture
    tempsOuverture = millis();
    return;
  }

  porteOuverte = true;
  tempsOuverture = millis();

  servoPorte.write(PORTE_OUVERTE);

  digitalWrite(PIN_LED_VERTE, HIGH);
  digitalWrite(PIN_LED_ROUGE, LOW);

  // Buzzer : petite mélodie montante à l'ouverture (do - mi - sol - do)
  const int notes[] = {523, 659, 784, 1047};
  for (int i = 0; i < 4; i++) {
    tone(PIN_BUZZER, notes[i]);
    delay(150);
  }
  noTone(PIN_BUZZER);

  afficherEtat("Porte ouverte", "Bienvenue !");
}


void fermerPorte() {
  porteOuverte = false;

  servoPorte.write(PORTE_FERMEE);

  digitalWrite(PIN_LED_VERTE, LOW);
  digitalWrite(PIN_LED_ROUGE, HIGH);

  tone(PIN_BUZZER, 500, 150);

  afficherEtat("Porte fermee", "En attente...");
}


// Commandes envoyées par le Python (test.py) : OUVRIR, FERMER, ETAT
void lireCommandes() {
  if (!Serial.available()) return;

  String commande = Serial.readStringUntil('\n');
  commande.trim();
  commande.toUpperCase();

  if (commande == "OUVRIR") {
    ouvrirPorte();
  } else if (commande == "FERMER") {
    if (porteOuverte) {
      fermerPorte();
    } else {
      Serial.println("ETAT: porte deja fermee");
    }
  } else if (commande == "ETAT") {
    Serial.print(porteOuverte ? "ETAT: porte ouverte" : "ETAT: porte fermee");
    Serial.print(", distance = ");
    Serial.print(distanceCm);
    Serial.println(" cm");
  } else if (commande.length() > 0) {
    Serial.print("Commande inconnue : ");
    Serial.println(commande);
  }
}


void setup() {
  Serial.begin(9600);
  Serial.setTimeout(50);

  // Configuration des broches
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BOUTON, INPUT_PULLUP);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);

  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_VERTE, OUTPUT);
  pinMode(PIN_LED_ROUGE, OUTPUT);

  // Etat initial : porte fermée, LED rouge allumée
  digitalWrite(PIN_LED_VERTE, LOW);
  digitalWrite(PIN_LED_ROUGE, HIGH);
  digitalWrite(PIN_BUZZER, LOW);

  // Initialisation du servo
  servoPorte.attach(PIN_SERVO);
  servoPorte.write(PORTE_FERMEE);

  // Initialisation du LCD I2C (adresse détectée automatiquement)
  Wire.begin();
  uint8_t adresse = trouverAdresseLCD();
  if (adresse != 0) {
    lcd = new LiquidCrystal_I2C(adresse, 16, 2);
    lcd->init();
    lcd->backlight();
    Serial.print("LCD trouve a l'adresse 0x");
    Serial.println(adresse, HEX);
  } else {
    Serial.println("LCD introuvable : verifier SDA->A4, SCL->A5, VCC->5V, GND");
  }

  afficherEtat("Hello World", "Demarrage...");

  // Le PIR a besoin d'un temps de stabilisation
  delay(2000);

  // On lit l'état réel du bouton pour éviter un faux appui au démarrage
  dernierEtatBouton = digitalRead(PIN_BOUTON);
  etatBoutonStable  = dernierEtatBouton;

  afficherEtat("Porte fermee", "En attente...");
}


void loop() {
  // ===== 1. CAPTEUR DE MOUVEMENT =====
  int etatPIR = digitalRead(PIN_PIR);

  if (etatPIR == HIGH && !mouvementDetecte) {
    mouvementDetecte = true;

    if (!porteOuverte) {
      afficherEtat("Mouvement !", "Porte verrouill.");
      tone(PIN_BUZZER, 700, 100);
    }
  }

  if (etatPIR == LOW && mouvementDetecte) {
    mouvementDetecte = false;

    if (!porteOuverte) {
      afficherEtat("Porte fermee", "En attente...");
    }
  }


  // ===== 2. BOUTON-POUSSOIR (avec anti-rebond) =====
  int lectureBouton = digitalRead(PIN_BOUTON);

  if (lectureBouton != dernierEtatBouton) {
    dernierChangementBouton = millis();
    dernierEtatBouton = lectureBouton;
  }

  if (millis() - dernierChangementBouton > ANTI_REBOND &&
      lectureBouton != etatBoutonStable) {
    etatBoutonStable = lectureBouton;

    // Le bouton vient d'être appuyé
    if (etatBoutonStable == LOW) {
      if (porteOuverte) {
        fermerPorte();
      } else {
        ouvrirPorte();
      }
    }
  }


  // ===== 3. CAPTEUR DE DISTANCE =====
  // Quelqu'un tout près : la porte s'ouvre, ou reste ouverte (elle ne se ferme pas sur lui)
  if (millis() - derniereMesure >= PERIODE_DISTANCE) {
    derniereMesure = millis();
    distanceCm = lireDistanceCm();

    if (distanceCm <= DISTANCE_OUVERTURE_CM) {
      ouvrirPorte();
    }
  }


  // ===== 4. FERMETURE AUTOMATIQUE =====
  if (porteOuverte && millis() - tempsOuverture >= DUREE_OUVERTURE) {
    fermerPorte();
  }


  // ===== 5. COMMANDES DU PC (Python) =====
  lireCommandes();

  delay(10);
}
