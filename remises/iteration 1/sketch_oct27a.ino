
#include <Servo.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>


// ===== COMPOSANTS =====
Servo servoPorte;


// Adresse LCD habituelle : 0x27
LiquidCrystal_I2C lcd(0x27, 16, 2);


// Broches
const int PIN_PIR = 0;
const int PIN_BOUTON = 2;
const int PIN_BUZZER = 8;
const int PIN_LED_VERTE = 11;
const int PIN_LED_ROUGE = 10;
const int PIN_SERVO = 9;


// Angles du servo
const int PORTE_FERMEE = 0;
const int PORTE_OUVERTE = 500;


// Temps avant fermeture automatique
const unsigned long DUREE_OUVERTURE = 3000;


// Variables
bool porteOuverte = false;
bool mouvementDetecte = false;


unsigned long tempsOuverture = 0;
unsigned long dernierChangementBouton = 0;


int dernierEtatBouton = HIGH;
int etatBoutonStable = HIGH;


void afficherEtat(const char* ligne1, const char* ligne2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(ligne1);
  lcd.setCursor(0, 1);
  lcd.print(ligne2);
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


  tone(PIN_BUZZER, 1000, 200);


  afficherEtat("Porte ouverte", "Bienvenue !");
}


void fermerPorte() {
  porteOuverte = false;


  servoPorte.write(PORTE_FERMEE);


  digitalWrite(PIN_LED_VERTE, LOW);
  digitalWrite(PIN_LED_ROUGE, HIGH);


  afficherEtat("Porte fermee", "En attente...");
}


void setup() {
  // Configuration des broches
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_BOUTON, INPUT_PULLUP);


  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_VERTE, OUTPUT);
  pinMode(PIN_LED_ROUGE, OUTPUT);


  // Initialisation du servo
  servoPorte.attach(PIN_SERVO);
  servoPorte.write(PORTE_FERMEE);


  // Initialisation du LCD I2C
  lcd.init();
  lcd.backlight();


  // Etat initial
  digitalWrite(PIN_LED_VERTE, LOW);
  digitalWrite(PIN_LED_ROUGE, HIGH);
  digitalWrite(PIN_BUZZER, LOW);


  afficherEtat("Porte intelligente", "Initialisation");


  // Le PIR a besoin d'un temps de stabilisation
  delay(2000);


  afficherEtat("Porte fermee", "En attente...");
}


void loop() {
  // ===== 1. CAPTEUR DE MOUVEMENT =====
  int etatPIR = digitalRead(PIN_PIR);


  if (etatPIR == HIGH && !mouvementDetecte) {
    mouvementDetecte = true;


    if (!porteOuverte) {
      afficherEtat("Mouvement detecte", "Porte verrouillee");
      tone(PIN_BUZZER, 700, 100);
    }
  }


  if (etatPIR == LOW && mouvementDetecte) {
    mouvementDetecte = false;


    if (!porteOuverte) {
      afficherEtat("Porte fermee", "En attente...");
    }
  }


  // ===== 2. BOUTON-POUSSOIR =====
  int lectureBouton = digitalRead(PIN_BOUTON);


  if (lectureBouton != dernierEtatBouton) {
    dernierChangementBouton = millis();
    dernierEtatBouton = lectureBouton;
  }


  if (millis() - dernierChangementBouton > 40) {
    if (lectureBouton != etatBoutonStable) {
      etatBoutonStable = lectureBouton;


      // Le bouton est appuye
      if (etatBoutonStable == LOW) {
        if (porteOuverte) {
          fermerPorte();
        } else {
          ouvrirPorte();
        }
      }
    }
  }


  // ===== 3. FERMETURE AUTOMATIQUE =====
  if (porteOuverte &&
      millis() - tempsOuverture >= DUREE_OUVERTURE) {
    fermerPorte();
  }


  delay(10);
}
 