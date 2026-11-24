"""
Itération 3 : Porte magique contrôlée par les gestes (MediaPipe)

Le Raspberry Pi (ou le PC) filme la main, reconnaît le geste avec la
librairie quickHand.py créée en classe, puis envoie la commande à l'Arduino
par le port série (porte_utils.py, même protocole qu'à l'itération 2).

Gestes reconnus :
    Main ouverte (5 doigts)   -> ouvrir la porte + mélodie
    Poing fermé (0 doigt)     -> fermer la porte
    1 doigt (index)           -> LED rouge
    2 doigts                  -> LED verte
    3 doigts                  -> sonnette « ding-dong » (buzzer)
    4 doigts                  -> LED en mode automatique
    Pouce levé                -> système ON
    Pouce baissé              -> système OFF
    Deux mains ouvertes       -> mode fête (LED qui clignotent + mélodie)

Un geste doit être tenu MAINTIEN_S secondes pour être validé : ça évite les
fausses détections quand la main bouge.

Touches : q ou Échap = quitter.
"""

import os
import queue
import shutil
import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp
import mediapipe.python.solution_base as mp_solution_base

import porte_utils
from quickHand import HandDetector


# ---------- Réglages ----------
MAINTIEN_S = 0.7          # durée pendant laquelle un geste doit être tenu
DELAI_ENTRE_ACTIONS = 1.0 # temps minimum entre deux actions
LARGEUR, HAUTEUR = 640, 480
FENETRE = "Porte magique - gestes"

# Couleurs (B, G, R)
VIOLET = (220, 90, 180)
VERT = (60, 200, 60)
ROUGE = (60, 60, 230)
BLANC = (240, 240, 240)
GRIS = (160, 160, 160)
JAUNE = (0, 210, 240)
FOND = (35, 30, 45)


# ---------- MediaPipe et les accents (« Collège ») ----------
def corriger_chemin_mediapipe():
    """MediaPipe (C++) ne lit pas les chemins avec accents. On copie ses modèles
    une seule fois dans %LOCALAPPDATA%\\mediapipe_ascii (même solution qu'à
    l'exercice 7). Sur le Raspberry Pi, le chemin n'a pas d'accent : rien à faire."""
    dossier = Path(mp.__file__).resolve().parent
    if str(dossier).isascii():
        return
    racine = Path(os.environ.get("LOCALAPPDATA", "C:/")) / "mediapipe_ascii"
    cible = racine / "mediapipe" / "modules"
    if not (cible / "hand_landmark").exists():
        print("Copie des modèles MediaPipe vers", cible, "...")
        shutil.copytree(dossier / "modules", cible, dirs_exist_ok=True)
    mp_solution_base.__file__ = str(racine / "mediapipe" / "python" / "solution_base.py")


# ---------- Caméra : Raspberry Pi (picamera2) ou webcam (OpenCV) ----------
class Camera:
    def __init__(self):
        self.picam = None
        self.webcam = None
        try:
            from picamera2 import Picamera2
            self.picam = Picamera2()
            config = self.picam.create_preview_configuration(
                main={"size": (LARGEUR, HAUTEUR), "format": "RGB888"})  # ordre BGR pour OpenCV
            self.picam.configure(config)
            self.picam.start()
            self.nom = "Camera Raspberry Pi"
        except Exception:
            self.picam = None
            self.webcam = cv2.VideoCapture(0)
            self.webcam.set(cv2.CAP_PROP_FRAME_WIDTH, LARGEUR)
            self.webcam.set(cv2.CAP_PROP_FRAME_HEIGHT, HAUTEUR)
            if not self.webcam.isOpened():
                raise RuntimeError("Caméra introuvable ou occupée (fermer l'app Caméra, Teams...).")
            self.nom = "Webcam"
        print(f"Caméra : {self.nom}")

    def lire(self):
        if self.picam is not None:
            return self.picam.capture_array()
        ok, image = self.webcam.read()
        return image if ok else None

    def fermer(self):
        if self.picam is not None:
            self.picam.stop()
        if self.webcam is not None:
            self.webcam.release()


# ---------- Reconnaissance du geste ----------
NOMS_GESTES = {
    "MAIN_OUVERTE": "Main ouverte",
    "POING": "Poing ferme",
    "UN": "1 doigt",
    "DEUX": "2 doigts",
    "TROIS": "3 doigts",
    "QUATRE": "4 doigts",
    "POUCE_HAUT": "Pouce leve",
    "POUCE_BAS": "Pouce baisse",
    "FETE": "Deux mains ouvertes",
}
PAR_NOMBRE = {0: "POING", 1: "UN", 2: "DEUX", 3: "TROIS", 4: "QUATRE", 5: "MAIN_OUVERTE"}


def geste_pouce(main):
    """POUCE_HAUT ou POUCE_BAS si le bout du pouce dépasse nettement
    le reste de la main vers le haut ou vers le bas, sinon None."""
    lm = main["lmList"]
    hauteur_main = main["bbox"][3]
    y_pouce = lm[4][2]
    y_autres = [lm[i][2] for i in range(5, 21)]   # tous les points des 4 autres doigts
    marge = 0.15 * hauteur_main
    if y_pouce < min(y_autres) - marge:
        return "POUCE_HAUT"
    if y_pouce > max(y_autres) + marge:
        return "POUCE_BAS"
    return None


def reconnaitre_geste(detecteur, mains):
    """Retourne le code du geste (voir NOMS_GESTES) ou None."""
    if not mains:
        return None

    # Deux mains grandes ouvertes : mode fête
    if len(mains) == 2 and all(detecteur.fingersUp(m) == 5 for m in mains):
        return "FETE"

    # Sinon on garde la main la plus proche (la plus grande à l'image)
    main = max(mains, key=lambda m: m["bbox"][2] * m["bbox"][3])
    doigts = detecteur.fingersList(main)

    # Seul le pouce est levé : vers le haut ou vers le bas ?
    if doigts == [1, 0, 0, 0, 0]:
        return geste_pouce(main)   # None si le pouce est sur le côté (ignoré)

    # Sinon : nombre de doigts levés
    nombre = sum(doigts)
    if nombre == 1 and doigts[1] != 1:
        return None   # un seul doigt, mais pas l'index : geste ambigu
    return PAR_NOMBRE[nombre]


class StabilisateurGeste:
    """Valide un geste seulement s'il est tenu MAINTIEN_S secondes,
    et ne le déclenche qu'une fois tant que la main ne change pas de geste."""

    def __init__(self):
        self.geste = None
        self.debut = 0.0
        self.deja_declenche = False
        self.derniere_action = 0.0

    def mettre_a_jour(self, geste):
        """Retourne le geste à déclencher maintenant, ou None."""
        maintenant = time.time()
        if geste != self.geste:
            self.geste = geste
            self.debut = maintenant
            self.deja_declenche = False
            return None
        if (geste is None or self.deja_declenche
                or maintenant - self.debut < MAINTIEN_S
                or maintenant - self.derniere_action < DELAI_ENTRE_ACTIONS):
            return None
        self.deja_declenche = True
        self.derniere_action = maintenant
        return geste

    def progression(self):
        """Entre 0 et 1 : avance de la barre de maintien à l'écran."""
        if self.geste is None:
            return 0.0
        if self.deja_declenche:
            return 1.0
        return min(1.0, (time.time() - self.debut) / MAINTIEN_S)


# ---------- Actions sur l'Arduino ----------
# Les actions avec des pauses (mélodies, clignotements) tournent dans un fil
# séparé pour que la vidéo ne gèle pas.
file_actions = queue.Queue()


def jouer_notes(notes, duree=0.15):
    porte_utils.activer_buzzer(True)
    for note in notes:
        porte_utils.buzzer(note)
        time.sleep(duree)
    porte_utils.buzzer(0)
    porte_utils.activer_buzzer(False)


def action_ouvrir():
    porte_utils.leds_automatiques()
    porte_utils.ouvrir("Geste magique")
    jouer_notes([523, 659, 784, 1047])


def action_fermer():
    porte_utils.leds_automatiques()
    porte_utils.fermer()


def action_led_rouge():
    porte_utils.regler_led_rouge(True)
    porte_utils.afficher_lcd("Geste : 1 doigt", "LED rouge")


def action_led_verte():
    porte_utils.regler_led_verte(True)
    porte_utils.afficher_lcd("Geste : 2 doigts", "LED verte")


def action_sonnette():
    porte_utils.afficher_lcd("Ding dong !", "Quelqu'un sonne")
    jouer_notes([784, 622], duree=0.4)


def action_leds_auto():
    porte_utils.leds_automatiques()
    porte_utils.afficher_lcd("Geste : 4 doigts", "LED automatiques")


def action_systeme_on():
    porte_utils.set_systeme(True)


def action_systeme_off():
    porte_utils.set_systeme(False)


def action_fete():
    porte_utils.afficher_lcd("Mode fete !", "Youpi !")
    porte_utils.activer_buzzer(True)
    notes = [523, 659, 784, 1047, 784, 659, 523, 1047]
    for i, note in enumerate(notes):
        porte_utils.regler_led_rouge(i % 2 == 0)   # les deux LED s'allument à tour de rôle
        porte_utils.regler_led_verte(i % 2 == 1)
        porte_utils.buzzer(note)
        time.sleep(0.2)
    porte_utils.buzzer(0)
    porte_utils.activer_buzzer(False)
    porte_utils.leds_automatiques()


ACTIONS = {
    "MAIN_OUVERTE": ("Ouvrir la porte", action_ouvrir),
    "POING": ("Fermer la porte", action_fermer),
    "UN": ("LED rouge", action_led_rouge),
    "DEUX": ("LED verte", action_led_verte),
    "TROIS": ("Sonnette", action_sonnette),
    "QUATRE": ("LED automatiques", action_leds_auto),
    "POUCE_HAUT": ("Systeme ON", action_systeme_on),
    "POUCE_BAS": ("Systeme OFF", action_systeme_off),
    "FETE": ("Mode fete", action_fete),
}


def executer_actions():
    """Fil d'exécution : exécute les actions une par une, dans l'ordre."""
    while True:
        geste = file_actions.get()
        description, fonction = ACTIONS[geste]
        print(f"Geste « {NOMS_GESTES[geste]} » -> {description}")
        fonction()


# ---------- Affichage ----------
def texte(image, contenu, position, couleur=BLANC, taille=0.55, epaisseur=1):
    cv2.putText(image, contenu, position, cv2.FONT_HERSHEY_SIMPLEX, taille, couleur, epaisseur)


def dessiner_panneau(image, geste, stabilisateur, derniere_action, fps):
    """Panneau à droite de la vidéo : geste détecté, action, état de l'Arduino."""
    panneau = cv2.copyMakeBorder(image, 0, 0, 0, 300, cv2.BORDER_CONSTANT, value=FOND)
    x = image.shape[1] + 15
    y = 35

    texte(panneau, "PORTE MAGIQUE", (x, y), VIOLET, 0.75, 2)
    y += 40

    # Geste détecté + barre de maintien
    texte(panneau, "Geste detecte :", (x, y), GRIS, 0.5)
    y += 28
    nom = NOMS_GESTES.get(geste, "Aucun") if geste else "Aucune main"
    texte(panneau, nom, (x, y), JAUNE if geste else GRIS, 0.7, 2)
    y += 15
    progression = stabilisateur.progression()
    cv2.rectangle(panneau, (x, y), (x + 260, y + 10), GRIS, 1)
    cv2.rectangle(panneau, (x, y), (x + int(260 * progression), y + 10),
                  VERT if progression >= 1 else JAUNE, -1)
    y += 40

    texte(panneau, "Derniere action :", (x, y), GRIS, 0.5)
    y += 26
    texte(panneau, derniere_action or "-", (x, y), VERT, 0.6, 2)
    y += 34

    # État réel de l'Arduino (reçu par STATUS), sur 3 lignes
    if porte_utils.est_connecte():
        actif = porte_utils.get_actif()
        texte(panneau, f"Systeme {'ON' if actif else 'OFF'} - {porte_utils.get_etat()}",
              (x, y), VERT if actif else ROUGE)
        y += 24
        cv2.circle(panneau, (x + 8, y - 5), 8, ROUGE if porte_utils.get_led_rouge() else GRIS, -1)
        cv2.circle(panneau, (x + 30, y - 5), 8, VERT if porte_utils.get_led_verte() else GRIS, -1)
        texte(panneau, f"LED   Distance: {porte_utils.get_distance()} cm", (x + 48, y))
        y += 22
        lcd = porte_utils.get_lcd()
        if lcd:
            texte(panneau, f"LCD: {lcd[0]} / {lcd[1]}"[:40], (x, y), GRIS, 0.4)
    else:
        texte(panneau, "Arduino non connecte", (x, y), ROUGE)

    # Aide : liste des gestes
    y = image.shape[0] - 9 * 18 - 30
    texte(panneau, "Gestes :", (x, y), GRIS, 0.45)
    for code, (description, _) in ACTIONS.items():
        y += 18
        texte(panneau, f"{NOMS_GESTES[code]} = {description}", (x, y), BLANC, 0.4)
    texte(panneau, f"{fps:.0f} FPS   q = quitter", (x, image.shape[0] - 10), GRIS, 0.4)
    return panneau


# ---------- Programme principal ----------
def main():
    corriger_chemin_mediapipe()
    detecteur = HandDetector(detectionCon=0.7, maxHands=2)
    camera = Camera()
    stabilisateur = StabilisateurGeste()
    threading.Thread(target=executer_actions, daemon=True).start()

    # Le système de la porte démarre OFF dans l'Arduino : on l'active
    # dès que le premier STATUS est reçu.
    time.sleep(1.5)
    porte_utils.set_systeme(True)

    derniere_action = ""
    temps_precedent = time.time()
    fps = 0.0
    cv2.namedWindow(FENETRE, cv2.WINDOW_NORMAL)

    try:
        while True:
            image = camera.lire()
            if image is None:
                continue
            image = cv2.flip(image, 1)   # effet miroir : plus naturel pour l'utilisateur

            # 1. Détection des mains avec la librairie du cours
            #    (image déjà en miroir : pas besoin d'inverser gauche/droite)
            mains, image = detecteur.findHands(image, draw=True, flipType=False)

            # 2. Reconnaissance du geste et validation
            geste = reconnaitre_geste(detecteur, mains)
            a_declencher = stabilisateur.mettre_a_jour(geste)

            # 3. Envoi de l'action à l'Arduino
            if a_declencher:
                derniere_action = ACTIONS[a_declencher][0]
                file_actions.put(a_declencher)

            # 4. Affichage
            for main in mains:
                detecteur.infoOnHand(image, main, [f"{detecteur.fingersUp(main)} doigts"])
            maintenant = time.time()
            fps = 0.9 * fps + 0.1 / max(maintenant - temps_precedent, 1e-3)
            temps_precedent = maintenant
            cv2.imshow(FENETRE, dessiner_panneau(image, geste, stabilisateur, derniere_action, fps))

            touche = cv2.waitKey(1) & 0xFF
            if touche in (ord("q"), 27) or cv2.getWindowProperty(FENETRE, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        camera.fermer()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
