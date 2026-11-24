# Porte magique

Une porte connectée : un Arduino gère les capteurs et les actionneurs, et un
Raspberry Pi (ou un PC) la contrôle par le port série (9600 bauds).

- **Itération 2** : tableau de bord ALIOT (`iteration2.py`).
- **Itération 3** : contrôle de la porte avec les gestes de la main grâce à MediaPipe (`iteration3_gestes.py`).

## Fichiers

| Fichier | Rôle |
|---|---|
| [porte_magique/porte_magique.ino](porte_magique/porte_magique.ino) | Code Arduino (itérations 2 et 3) |
| [porte_utils.py](porte_utils.py) | Communication série avec l'Arduino, utilisée par tous les programmes Python |
| [quickHand.py](quickHand.py) | Librairie de détection des mains créée en classe |
| [iteration3_gestes.py](iteration3_gestes.py) | **Itération 3** : les gestes contrôlent la porte |
| [tableau_aliot.py](tableau_aliot.py) | Itération 3 : envoie le geste et l'état de la porte aux 2 objets ALIOT (`rasp_door` et `porte_magique`) |
| [iteration2.py](iteration2.py) | Itération 2 : tableau de bord ALIOT |
| [log.py](log.py) | Itération 2 : version simplifiée pour ALIOT |
| [config.ini](config.ini) | Identifiants des objets ALIOT |
| [requirements.txt](requirements.txt) | Librairies Python à installer |

## Montage (broches réelles)

| Composant | Broche Arduino |
|---|---|
| Ultrason HC-SR04 | TRIG **3**, ECHO **2** |
| Buzzer | **4** |
| LED rouge | **6** (+ résistance 220 Ω) |
| LED verte | **7** (+ résistance 220 Ω) |
| Bouton poussoir (ON / OFF) | **10** (l'autre patte au GND) |
| Écran LCD 16x2 I2C | SDA **A4**, SCL **A5** |
| Caméra | Port CSI du Raspberry Pi, ou webcam USB |

## Itération 3 : les gestes

| Geste | Action sur la porte |
|---|---|
| Main ouverte (5 doigts) | Ouvre la porte : LED verte, LCD « Porte ouverte », mélodie |
| Poing fermé | Ferme la porte |
| 1 doigt (index) | Allume la LED rouge |
| 2 doigts | Allume la LED verte |
| 3 doigts | Sonnette « ding-dong » avec le buzzer |
| 4 doigts | Les LED reviennent en mode automatique |
| Pouce levé | Active le système |
| Pouce baissé | Désactive le système |
| Deux mains ouvertes | Mode fête : les LED clignotent à tour de rôle, avec une mélodie |

Fonctionnement :

1. La caméra filme la main, et `quickHand.py` (`findHands`, `fingersList`, `fingersUp`) trouve les doigts levés.
2. Un geste doit être tenu **0,7 seconde** pour être validé : la barre à l'écran se remplit. Il n'est déclenché qu'une fois tant que la main ne change pas de geste.
3. Le programme envoie la commande à l'Arduino par le port série (`porte_utils.py`).
4. La fenêtre affiche le geste détecté, la dernière action et l'état réel de l'Arduino (système, LED, distance, texte du LCD). L'écran LCD affiche aussi le geste.
5. Le geste, l'action et l'état de la porte sont publiés sur les tableaux de bord ALIVEcode (`/doc/geste`, `/doc/action_geste`, `/doc/etat`...). Les boutons des tableaux de bord de l'itération 2 marchent aussi pendant ce temps.

Amélioration de la librairie : `fingersList()` compare des **distances** au lieu
des coordonnées x et y. Le comptage des doigts marche donc même si la main est
penchée, et peu importe que ce soit la main gauche ou la main droite.

## Lancer le programme

**Sur le PC (Windows)**, depuis le dossier du projet :

```powershell
.\venv_mediapipe\Scripts\python.exe "porte magique\iteration3_gestes.py"
```

**Sur le Raspberry Pi** :

```bash
sudo apt install python3-picamera2 python3-opencv
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
python iteration3_gestes.py
```

Le port de l'Arduino est détecté automatiquement. Pour l'imposer :
`$env:PORTE_PORT = "COM6"` (Windows) ou `export PORTE_PORT=/dev/ttyACM0` (Pi).

**Avant de lancer** : fermer le Moniteur série d'Arduino IDE (sinon le port est
occupé) et toute autre application qui utilise la caméra.

## Limites observées (tests en conditions réelles)

À compléter après les tests. Points à vérifier :

- **Éclairage** : en contre-jour ou dans le noir, la main n'est pas détectée.
- **Distance** : à plus de 2 m environ, la main est trop petite pour compter les doigts.
- **Fausses détections** : une main qui passe vite est ignorée grâce au maintien de 0,7 s. Le pouce sur le côté (ni levé ni baissé) est volontairement ignoré.
- **Pouce levé / baissé** : il faut garder les 4 autres doigts bien pliés.
- **Vitesse** : environ 15 à 25 images par seconde sur PC, moins sur Raspberry Pi.

## Itération 2 : ALIOT

Installer `aliot-py` et `pyserial`, puis lancer `iteration2.py`. Les identifiants
des objets sont dans [config.ini](config.ini). La variable `PORTE_OBJET` choisit l'objet :
`rasp_door` (Raspberry Pi, par défaut) ou `porte_magique`.
