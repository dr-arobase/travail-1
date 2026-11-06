/*
 * Itération 2 - Porte magique (côté Arduino)
 *
 * Matériel :
 *   1. Afficheur LCD I2C 16x2   -> messages (« Bienvenue Massyle », « Acces refuse »...)
 *   2. LED verte                -> accès autorisé (porte ouverte)
 *   3. LED rouge                -> accès refusé / système désactivé
 *   4. Buzzer                   -> mélodie d'ouverture, son de refus, alarme
 *   5. Capteur ultrason HC-SR04 -> détecte une personne devant la porte
 *   6. Bouton poussoir          -> active / désactive le système
 *
 * Communication série (9600 bauds) avec le PC (iteration2.py) :
 *   Arduino -> PC : STATUS:actif=1,etat=VEILLE,presence=0,distance=120,angle=0,ledR=0,ledV=0
 *                   LCD:<ligne1>|<ligne2>   EVT:<evenement>   INFO:<texte>
 *   PC -> Arduino : OPEN:<nom>, CLOSE, DENY, TOGGLE, STATUS,
 *                   MSG:<ligne1>|<ligne2>, BUZZ:<frequence> (BUZZ:0 = silence),
 *                   BUZZER:ON/OFF, LED:ROUGE:ON/OFF, LED:VERTE:ON/OFF,
 *                   LED:OFF, LED:AUTO
 *
 * Bibliothèque : LiquidCrystal I2C (Frank de Brabander)
 */

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ---------- Broches ----------
const uint8_t PIN_BOUTON    = 8;   // broche 8, l'autre patte du bouton va au GND
const uint8_t PIN_TRIG      = 3;
const uint8_t PIN_ECHO      = 2;
const uint8_t PIN_BUZZER    = 4;
const uint8_t PIN_LED_ROUGE = 6;
const uint8_t PIN_LED_VERTE = 7;
// LCD I2C : SDA -> A4, SCL -> A5

// ---------- Paramètres ----------
const int DIST_PRESENCE_CM = 5;             // porte ouverte si un objet est sous cette distance
const int  ANGLE_FERME  = 0;                 // porte virtuelle (pas de servo)
const int  ANGLE_OUVERT = 90;
const unsigned long DUREE_OUVERTURE     = 5000;
const unsigned long DUREE_REFUS         = 3000;
const unsigned long DELAI_RETOUR_VEILLE = 10000;
const unsigned long PERIODE_CAPTEUR     = 100;
const unsigned long PERIODE_STATUS      = 1000;
const unsigned long ANTI_REBOND         = 50;

// ---------- Mélodies (fréquences en Hz) ----------
const int MELODIE_OUVERTURE[] = {523, 659, 784, 1047};
const int MELODIE_REFUS[]     = {330, 220};

// ---------- Objets ----------
LiquidCrystal_I2C lcd(0x27, 16, 2);  // essayer 0x3F si l'écran reste vide

// ---------- État ----------
enum Etat { VEILLE, PRESENCE, OUVERTE, REFUSEE };
const char* NOMS_ETAT[] = {"VEILLE", "PRESENCE", "OUVERTE", "REFUSEE"};
Etat etat = VEILLE;

bool systemeActif = false;
bool presence = false;
bool ledRouge = false;
bool ledVerte = false;
bool buzzerActif = false;
bool ledsAutomatiques = true;
int  distanceCm = 999;
int  angle = ANGLE_FERME;
int  frequenceAlarme = 0;
String nomVisiteur = "";

unsigned long tEtat = 0;
unsigned long tDernierePresence = 0;
unsigned long tCapteur = 0;
unsigned long tStatus = 0;
bool lcdAMettreAJour = true;

const int* melodie = nullptr;
uint8_t longueurMelodie = 0;
uint8_t indexNote = 0;
unsigned long dureeNote = 0;
unsigned long tNote = 0;

bool etatBoutonStable  = HIGH;
bool dernierEtatBouton = HIGH;
bool boutonTraite = false;
unsigned long tRebond  = 0;

String tampon = "";

// ======================================================================
void setup() {
  Serial.begin(9600);

  pinMode(PIN_BOUTON, INPUT_PULLUP);
  etatBoutonStable = HIGH;
  dernierEtatBouton = HIGH;
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_LED_ROUGE, OUTPUT);
  pinMode(PIN_LED_VERTE, OUTPUT);

  lcd.init();
  lcd.backlight();
  afficher("Porte magique", "Systeme OFF");
  delay(1000);
  lcdAMettreAJour = true;

  Serial.println(F("INFO:Arduino pret"));
  envoyerStatus();
}

void loop() {
  unsigned long maintenant = millis();

  lireBouton();
  lireSerie();

  if (maintenant - tCapteur >= PERIODE_CAPTEUR) {
    tCapteur = maintenant;
    distanceCm = lireDistanceCm();
    presence = distanceCm <= DIST_PRESENCE_CM;
    if (presence) tDernierePresence = maintenant;
  }

  if (systemeActif) gererEtats();
  gererLeds();
  gererMelodie();

  if (maintenant - tStatus >= PERIODE_STATUS) {
    tStatus = maintenant;
    envoyerStatus();
  }
  if (lcdAMettreAJour) majAffichage();
}

// ---------- Machine à états de la porte ----------
void gererEtats() {
  unsigned long ecoule = millis() - tEtat;

  switch (etat) {
    case VEILLE:
      if (presence) {
        ouvrirPorte("Ami");
        Serial.println(F("EVT:PRESENCE_DETECTEE"));
      }
      break;

    case PRESENCE:
      if (millis() - tDernierePresence > DELAI_RETOUR_VEILLE) {
        changerEtat(VEILLE);
        Serial.println(F("EVT:VEILLE"));
      }
      break;

    case OUVERTE:
      if (!presence && ecoule > DUREE_OUVERTURE) fermerPorte();
      break;

    case REFUSEE:
      if (ecoule > DUREE_REFUS) changerEtat(presence ? PRESENCE : VEILLE);
      break;
  }
}

void changerEtat(Etat nouveau) {
  etat = nouveau;
  tEtat = millis();
  lcdAMettreAJour = true;
}

void ouvrirPorte(const String& nom) {
  nomVisiteur = nom;
  angle = ANGLE_OUVERT;
  changerEtat(OUVERTE);
  melodie = nullptr;
  if (buzzerActif) {
    tone(PIN_BUZZER, 1000, 3000);
  } else {
    noTone(PIN_BUZZER);
  }
  Serial.print(F("EVT:PORTE_OUVERTE:"));
  Serial.println(nom);
}

void fermerPorte() {
  angle = ANGLE_FERME;
  changerEtat(presence ? PRESENCE : VEILLE);
  Serial.println(F("EVT:PORTE_FERMEE"));
}

void refuserAcces() {
  angle = ANGLE_FERME;
  changerEtat(REFUSEE);
  jouerMelodie(MELODIE_REFUS, 2, 300);
  Serial.println(F("EVT:ACCES_REFUSE"));
}

void basculerSysteme() {
  systemeActif = !systemeActif;
  angle = ANGLE_FERME;
  ledsAutomatiques = true;
  melodie = nullptr;
  noTone(PIN_BUZZER);
  changerEtat(VEILLE);
  if (systemeActif) {
    afficher("Porte fermer", "Systeme ON");
    Serial.println(F("EVT:SYSTEME_ON"));
  } else {
    afficher("Porte magique", "Systeme OFF");
    Serial.println(F("EVT:SYSTEME_OFF"));
  }
}

// ---------- Bouton poussoir (avec anti-rebond) ----------
void lireBouton() {
  const bool lecture = digitalRead(PIN_BOUTON);
  if (lecture != dernierEtatBouton) {
    tRebond = millis();
    dernierEtatBouton = lecture;
  }
  if (millis() - tRebond < ANTI_REBOND) return;

  if (lecture != etatBoutonStable) {
    etatBoutonStable = lecture;
    if (etatBoutonStable == LOW && !boutonTraite) {
      boutonTraite = true;
      Serial.println(F("EVT:BOUTON"));
      basculerSysteme();
    } else if (etatBoutonStable == HIGH) {
      boutonTraite = false;
    }
  }
}

// ---------- Capteur ultrason ----------
int lireDistanceCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  unsigned long duree = pulseIn(PIN_ECHO, HIGH, 25000UL);  // ~4 m max
  if (duree == 0) return 999;                             // rien détecté
  return duree / 58;
}

// ---------- LED verte et LED rouge ----------
void setLeds(bool verte, bool rouge) {
  ledVerte = verte;
  ledRouge = rouge;
  digitalWrite(PIN_LED_VERTE, verte);
  digitalWrite(PIN_LED_ROUGE, rouge);
}

void gererLeds() {
  if (!ledsAutomatiques) return;
  if (!systemeActif) {             // système OFF : rouge fixe
    setLeds(false, true);
    return;
  }
  switch (etat) {
    case OUVERTE: setLeds(true, false);                 break;
    case REFUSEE: setLeds(false, (millis() / 200) % 2); break;  // rouge clignotant
    default:      setLeds(false, true);                 break;  // porte fermée
  }
}

void reglerLedsManuellement(bool rouge, bool verte) {
  ledsAutomatiques = false;
  setLeds(verte, rouge);
  Serial.print(F("EVT:LED_MANUELLE:"));
  if (rouge && !verte) {
    Serial.println(F("ROUGE"));
  } else if (verte && !rouge) {
    Serial.println(F("VERTE"));
  } else {
    Serial.println(F("OFF"));
  }
}

void reglerLedManuellement(bool rouge, bool allumee) {
  ledsAutomatiques = false;
  if (rouge) {
    setLeds(ledVerte, allumee);
  } else {
    setLeds(allumee, ledRouge);
  }
}

// ---------- Buzzer : mélodie non bloquante + alarme ----------
void jouerMelodie(const int* notes, uint8_t longueur, unsigned long duree) {
  if (!buzzerActif) {
    melodie = nullptr;
    noTone(PIN_BUZZER);
    return;
  }
  melodie = notes;
  longueurMelodie = longueur;
  indexNote = 0;
  dureeNote = duree;
  tNote = millis() - duree;  // la première note part tout de suite
}

void gererMelodie() {
  if (!buzzerActif) {
    melodie = nullptr;
    noTone(PIN_BUZZER);
    return;
  }
  if (melodie == nullptr || millis() - tNote < dureeNote) return;
  if (indexNote >= longueurMelodie) {
    melodie = nullptr;
    if (frequenceAlarme > 0) {
      tone(PIN_BUZZER, frequenceAlarme);   // l'alarme reprend après la mélodie
    } else {
      noTone(PIN_BUZZER);
    }
    return;
  }
  tone(PIN_BUZZER, melodie[indexNote], dureeNote * 9 / 10);
  indexNote++;
  tNote = millis();
}

void reglerAlarme(int frequence) {
  frequenceAlarme = frequence;
  if (!buzzerActif || melodie != nullptr) return;  // l'alarme démarre après la mélodie
  if (frequence > 0) {
    tone(PIN_BUZZER, frequence);
  } else {
    noTone(PIN_BUZZER);
  }
}

void reglerBuzzer(bool actif) {
  buzzerActif = actif;
  melodie = nullptr;
  if (!actif) {
    noTone(PIN_BUZZER);
  }
  Serial.print(F("EVT:BUZZER_"));
  Serial.println(actif ? F("ON") : F("OFF"));
}

// ---------- Afficheur LCD ----------
void afficher(const String& ligne1, const String& ligne2) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(ligne1.substring(0, 16));
  lcd.setCursor(0, 1);
  lcd.print(ligne2.substring(0, 16));

  // On envoie au PC ce qui est réellement affiché sur l'écran
  Serial.print(F("LCD:"));
  Serial.print(ligne1.substring(0, 16));
  Serial.print('|');
  Serial.println(ligne2.substring(0, 16));
}

void majAffichage() {
  lcdAMettreAJour = false;
  if (!systemeActif) {
    afficher("Porte magique", "Systeme OFF");
    return;
  }
  switch (etat) {
    case VEILLE:   afficher("Porte fermer", "Systeme ON");   break;
    case PRESENCE: afficher("Bonjour !", "Bienvenue ici");   break;
    case OUVERTE:  afficher("Porte ouverte", nomVisiteur);   break;
    case REFUSEE:  afficher("Acces refuse", "Desole...");    break;
    
  }
}

// ---------- Communication série ----------
void lireSerie() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      tampon.trim();
      traiterCommande(tampon);
      tampon = "";
    } else if (tampon.length() < 40) {
      tampon += c;
    }
  }
}

void traiterCommande(const String& cmd) {
  if (cmd == "OPEN" || cmd.startsWith("OPEN:")) {
    if (systemeActif) {
      ouvrirPorte(cmd.length() > 5 ? cmd.substring(5) : String("Ami"));
    }
  } else if (cmd == "DENY") {
    if (systemeActif) refuserAcces();
  } else if (cmd == "CLOSE") {
    if (etat == OUVERTE) fermerPorte();
  } else if (cmd == "TOGGLE") {
    basculerSysteme();
  } else if (cmd == "STATUS") {
    envoyerStatus();
  } else if (cmd.startsWith("MSG:")) {
    // Message envoyé depuis l'interface ALIVEcode : MSG:ligne1|ligne2
    String texte = cmd.substring(4);
    int separateur = texte.indexOf('|');
    if (separateur >= 0) {
      afficher(texte.substring(0, separateur), texte.substring(separateur + 1));
    } else {
      afficher(texte, "");
    }
    Serial.println(F("EVT:LCD_MESSAGE"));
  } else if (cmd == "BUZZER:ON") {
    reglerBuzzer(true);
  } else if (cmd == "BUZZER:OFF") {
    reglerBuzzer(false);
  } else if (cmd == "LED:ROUGE:ON") {
    reglerLedsManuellement(true, false);
  } else if (cmd == "LED:ROUGE:OFF") {
    reglerLedManuellement(true, false);
  } else if (cmd == "LED:VERTE:ON") {
    reglerLedsManuellement(false, true);
  } else if (cmd == "LED:VERTE:OFF") {
    reglerLedManuellement(false, false);
  } else if (cmd == "LED:OFF") {
    reglerLedsManuellement(false, false);
  } else if (cmd == "LED:AUTO") {
    ledsAutomatiques = true;
    Serial.println(F("EVT:LED_AUTOMATIQUE"));
  } else if (cmd.startsWith("BUZZ:")) {
    reglerAlarme(cmd.substring(5).toInt());
  } else if (cmd.length() > 0) {
    Serial.print(F("INFO:Commande inconnue "));
    Serial.println(cmd);
  }
}

void envoyerStatus() {
  Serial.print(F("STATUS:actif="));
  Serial.print(systemeActif);
  Serial.print(F(",etat="));
  Serial.print(NOMS_ETAT[etat]);
  Serial.print(F(",presence="));
  Serial.print(presence);
  Serial.print(F(",distance="));
  Serial.print(distanceCm);
  Serial.print(F(",angle="));
  Serial.print(angle);
  Serial.print(F(",ledR="));
  Serial.print(ledRouge);
  Serial.print(F(",ledV="));
  Serial.print(ledVerte);
  Serial.print(F(",bouton="));
  Serial.println(digitalRead(PIN_BOUTON) == LOW ? 0 : 1);
}
