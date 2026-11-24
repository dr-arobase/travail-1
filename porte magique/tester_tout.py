"""
Tests de la porte magique (itération 3).

Vérifie, dans l'ordre :
    1. l'environnement Python (venv) et ses librairies
    2. MediaPipe (avec le correctif des accents) et la librairie quickHand
    3. la reconnaissance des 9 gestes (mains simulées)
    4. la validation des gestes (maintien de 0,7 s)
    5. la caméra et la détection des mains en direct
    6. l'Arduino : chaque commande série et la réponse réelle de la carte
    7. les deux objets ALIOT : connexion, écriture et relecture dans leur projet

Utilisation (fermer d'abord la porte et le Moniteur série, ils occupent le port) :
    .\\venv\\Scripts\\python.exe tester_tout.py      (depuis le dossier « porte magique »)
Sans matériel, pendant que la porte tourne (tests 1 à 4 seulement) : ajouter --logiciel
"""

import os
import sys
import time

for flux in (sys.stdout, sys.stderr):
    try:
        flux.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

os.chdir(os.path.dirname(os.path.abspath(__file__)))

resultats = []   # (partie, test, réussi, détail)


def verifier(partie, test, condition, detail=""):
    resultats.append((partie, test, bool(condition), detail))
    print(f"  {'OK   ' if condition else 'ECHEC'} {test}" + (f"  ({detail})" if detail else ""))
    return bool(condition)


def titre(texte):
    print(f"\n=== {texte} ===")


def bilan():
    titre("Bilan")
    reussis = sum(1 for r in resultats if r[2])
    print(f"{reussis} / {len(resultats)} tests réussis")
    for partie, test, ok, detail in resultats:
        if not ok:
            print(f"  ÉCHEC - {partie} : {test}" + (f" ({detail})" if detail else ""))
    sys.exit(0 if reussis == len(resultats) else 1)


# ---------------------------------------------------------------------------
titre("1. Environnement Python")
verifier("Environnement", "Python 3.12 (compatible MediaPipe)",
         sys.version_info[:2] == (3, 12), sys.version.split()[0])
verifier("Environnement", "Python du venv de « porte magique »",
         os.path.normcase(os.path.join("porte magique", "venv")) in os.path.normcase(sys.prefix), sys.prefix)

librairies = {}
for nom in ("mediapipe", "cv2", "numpy", "serial", "aliot"):
    try:
        module = __import__(nom)
        librairies[nom] = getattr(module, "__version__", "ok")
        verifier("Environnement", f"import {nom}", True, librairies[nom])
    except Exception as erreur:
        verifier("Environnement", f"import {nom}", False, str(erreur))

# ---------------------------------------------------------------------------
titre("2. MediaPipe et quickHand")
import cv2
import numpy as np

import iteration3_gestes as g
import porte_utils
import tableau_aliot

try:
    g.corriger_chemin_mediapipe()
    detecteur = g.HandDetector(detectionCon=0.7, maxHands=2)
    verifier("MediaPipe", "Création du détecteur de mains (chemin avec accents)", True)
except Exception as erreur:
    detecteur = None
    verifier("MediaPipe", "Création du détecteur de mains (chemin avec accents)", False, str(erreur))

if detecteur:
    mains = detecteur.findHands(np.zeros((480, 640, 3), np.uint8), draw=False, flipType=False)
    verifier("MediaPipe", "Image vide : aucune main détectée", mains == [])


# ---------------------------------------------------------------------------
titre("3. Reconnaissance des gestes (mains simulées)")


def main_simulee(doigts, pouce=None):
    """Points MediaPipe (id, x, y) d'une main, poignet en bas."""
    points = [[0, 320, 400]]
    if pouce == "haut":
        pouce_xy = [(300, 360), (290, 320), (285, 280), (282, 230)]
    elif pouce == "bas":
        pouce_xy = [(300, 420), (290, 450), (285, 480), (282, 520)]
    elif doigts[0]:
        pouce_xy = [(290, 380), (260, 360), (235, 345), (210, 330)]
    else:
        pouce_xy = [(290, 380), (300, 350), (320, 345), (340, 350)]
    points += [[i + 1, x, y] for i, (x, y) in enumerate(pouce_xy)]
    for f, x in enumerate([300, 320, 340, 360]):
        if pouce:
            ys = [330, 320, 335, 345]          # poing de côté
        elif doigts[f + 1]:
            ys = [330, 290, 260, 230]          # doigt tendu
        else:
            ys = [330, 310, 330, 350]          # doigt replié
        points += [[5 + 4 * f + k, x, ys[k]] for k in range(4)]
    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    return {"lmList": points, "bbox": (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)),
            "type": "Right", "center": (0, 0)}


if detecteur:
    cas = [
        ("Main ouverte", [main_simulee([1, 1, 1, 1, 1])], "MAIN_OUVERTE"),
        ("Poing", [main_simulee([0, 0, 0, 0, 0])], "POING"),
        ("1 doigt", [main_simulee([0, 1, 0, 0, 0])], "UN"),
        ("2 doigts", [main_simulee([0, 1, 1, 0, 0])], "DEUX"),
        ("3 doigts", [main_simulee([0, 1, 1, 1, 0])], "TROIS"),
        ("4 doigts", [main_simulee([0, 1, 1, 1, 1])], "QUATRE"),
        ("Pouce levé", [main_simulee([1, 0, 0, 0, 0], "haut")], "POUCE_HAUT"),
        ("Pouce baissé", [main_simulee([1, 0, 0, 0, 0], "bas")], "POUCE_BAS"),
        ("Deux mains ouvertes", [main_simulee([1] * 5), main_simulee([1] * 5)], "FETE"),
        ("Aucune main", [], None),
        ("Auriculaire seul (ambigu, ignoré)", [main_simulee([0, 0, 0, 0, 1])], None),
    ]
    for nom, mains, attendu in cas:
        obtenu = g.reconnaitre_geste(detecteur, mains)
        verifier("Gestes", nom, obtenu == attendu, f"obtenu {obtenu}")
    verifier("Gestes", "Chaque geste a une action", set(g.ACTIONS) == set(g.NOMS_GESTES))

# ---------------------------------------------------------------------------
titre("4. Validation des gestes (maintien)")
s = g.StabilisateurGeste()
verifier("Validation", "Geste tout juste apparu : pas d'action", s.mettre_a_jour("POING") is None)
time.sleep(g.MAINTIEN_S + 0.1)
verifier("Validation", f"Geste tenu {g.MAINTIEN_S} s : action déclenchée", s.mettre_a_jour("POING") == "POING")
verifier("Validation", "Geste toujours tenu : pas de 2e déclenchement", s.mettre_a_jour("POING") is None)
s.mettre_a_jour("UN")
time.sleep(g.MAINTIEN_S + 0.1)
verifier("Validation", "Changement de geste trop vite (< 1 s) : bloqué", s.mettre_a_jour("UN") is None)
time.sleep(g.DELAI_ENTRE_ACTIONS)
verifier("Validation", "Après le délai : le nouveau geste passe", s.mettre_a_jour("UN") == "UN")

# Option --logiciel : seulement les tests 1 à 4 (sans caméra, Arduino ni ALIOT),
# par exemple pendant que la porte tourne déjà.
if "--logiciel" in sys.argv:
    print("\n(--logiciel : caméra, Arduino et ALIOT non testés)")
    bilan()

# ---------------------------------------------------------------------------
titre("5. Caméra et détection en direct")
camera = None
try:
    camera = g.Camera()
    verifier("Caméra", "Ouverture de la caméra", True, camera.nom)
except Exception as erreur:
    verifier("Caméra", "Ouverture de la caméra", False, str(erreur))

if camera and detecteur:
    debut, images = time.time(), 0
    while time.time() - debut < 3:
        image = camera.lire()
        if image is None:
            continue
        mains, _ = detecteur.findHands(cv2.flip(image, 1), draw=True, flipType=False)
        images += 1
    fps = images / (time.time() - debut)
    verifier("Caméra", "Lecture d'images", images > 0, f"{images} images")
    verifier("Caméra", "Vitesse suffisante (> 8 images/s)", fps > 8, f"{fps:.1f} images/s")
    panneau = g.dessiner_panneau(cv2.flip(image, 1), None, g.StabilisateurGeste(), "", fps)
    verifier("Caméra", "Dessin du panneau d'affichage", panneau.shape[1] == image.shape[1] + 300)
    camera.fermer()

# ---------------------------------------------------------------------------
titre("6. Arduino (commandes réelles)")


def attendre(condition, delai=4.0):
    fin = time.time() + delai
    while time.time() < fin:
        if condition():
            return True
        time.sleep(0.1)
    return False


if verifier("Arduino", "Connexion série", attendre(porte_utils.est_connecte, 8)):
    verifier("Arduino", "Réception de l'état (STATUS)", attendre(lambda: porte_utils.get_distance() is not None))
    verifier("Arduino", "Ultrason : distance lue", porte_utils.get_distance() not in (None,),
             f"{porte_utils.get_distance()} cm")

    porte_utils.set_systeme(False)
    attendre(lambda: not porte_utils.get_actif())
    verifier("Arduino", "Système OFF : LED éteintes",
             attendre(lambda: not porte_utils.get_led_rouge() and not porte_utils.get_led_verte()))
    verifier("Arduino", "Système OFF : LCD « Systeme OFF »",
             attendre(lambda: (porte_utils.get_lcd() or ("", ""))[1] == "Systeme OFF"))

    porte_utils.set_systeme(True)
    verifier("Arduino", "Système ON (pouce levé / bouton)", attendre(porte_utils.get_actif))
    verifier("Arduino", "Système ON : LED rouge (porte fermée)", attendre(porte_utils.get_led_rouge))

    porte_utils.regler_led_verte(True)
    verifier("Arduino", "LED verte manuelle (2 doigts)",
             attendre(lambda: porte_utils.get_led_verte() and not porte_utils.get_led_rouge()))
    porte_utils.regler_led_rouge(True)
    verifier("Arduino", "LED rouge manuelle (1 doigt)",
             attendre(lambda: porte_utils.get_led_rouge() and not porte_utils.get_led_verte()))
    porte_utils.eteindre_leds()
    verifier("Arduino", "LED éteintes", attendre(lambda: not porte_utils.get_led_rouge() and not porte_utils.get_led_verte()))
    porte_utils.leds_automatiques()
    verifier("Arduino", "LED automatiques (4 doigts)", attendre(porte_utils.get_led_rouge))

    porte_utils.afficher_lcd("Test LCD", "Bonjour")
    verifier("Arduino", "Message sur le LCD", attendre(lambda: porte_utils.get_lcd() == ("Test LCD", "Bonjour")))

    porte_utils.get_evenements()
    porte_utils.activer_buzzer(True)
    verifier("Arduino", "Buzzer activé", attendre(lambda: "BUZZER_ON" in porte_utils.get_evenements()))
    porte_utils.buzzer(0)
    porte_utils.activer_buzzer(False)
    verifier("Arduino", "Buzzer désactivé", attendre(lambda: "BUZZER_OFF" in porte_utils.get_evenements()))

    porte_utils.ouvrir("Test")
    verifier("Arduino", "Ouvrir la porte (main ouverte)",
             attendre(lambda: porte_utils.get_etat() == "OUVERTE" and porte_utils.get_led_verte()))
    verifier("Arduino", "Servo (broche 9) : la porte s'ouvre (60°)",
             attendre(lambda: porte_utils.get_angle() == 60, 5), f"{porte_utils.get_angle()}°")
    porte_utils.fermer()
    verifier("Arduino", "Fermer la porte (poing)",
             attendre(lambda: porte_utils.get_etat() != "OUVERTE" and porte_utils.get_led_rouge()))

    # Main ouverte alors que la porte est verrouillée (système OFF) : accès refusé
    porte_utils.set_systeme(False)
    attendre(lambda: not porte_utils.get_actif())
    g.action_ouvrir()
    verifier("Arduino", "Porte verrouillée + main ouverte : accès refusé",
             porte_utils.get_lcd() == ("Acces refuse", "Porte verrouill.") and porte_utils.get_etat() != "OUVERTE",
             f"LCD {porte_utils.get_lcd()}")
    verifier("Arduino", "Accès refusé : la porte reste fermée (servo à 155°)",
             attendre(lambda: porte_utils.get_angle() == 155, 3), f"{porte_utils.get_angle()}°")

# ---------------------------------------------------------------------------
titre("7. Objets ALIOT (projets ALIVEcode)")
tableau_aliot.demarrer()
fin = time.time() + 20
while time.time() < fin and len(tableau_aliot.objets_connectes()) < len(tableau_aliot.objets):
    time.sleep(0.5)

for objet in tableau_aliot.objets:
    nom = objet.name
    if not verifier("ALIOT", f"{nom} : connecté à ALIVEcode", objet.connected_to_alivecode):
        continue
    valeur = int(time.time())
    objet.update_doc({"/doc/test_connexion": valeur})
    time.sleep(2)
    relu = objet.get_doc("/doc/test_connexion")
    verifier("ALIOT", f"{nom} : relié à un projet (écriture puis relecture du document)",
             relu == valeur, f"relu {relu}")

for objet in tableau_aliot.objets:
    objet.stop()

bilan()
