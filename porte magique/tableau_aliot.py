"""
Tableau de bord ALIOT pour l'itération 3.

Connecte la porte aux DEUX objets ALIVEcode pendant que iteration3_gestes.py tourne :
    rasp_door      (Raspberry Pi d'Ernst)
    porte_magique  (objet de Massyle)

Pour chaque objet :
- publie le geste détecté, la dernière action et l'état de l'Arduino ;
- accepte les boutons des interfaces de l'itération 2 (ouvrir, fermer, LED, buzzer...).

La variable PORTE_OBJETS permet de choisir les objets, par exemple :
    $env:PORTE_OBJETS = "rasp_door"
Si ALIOT n'est pas installé ou que le réseau est absent, la porte marche
quand même avec les gestes, sans tableau de bord.
"""

import os
import sys
import threading
import time

import porte_utils

# La librairie ALIOT affiche des symboles (▽, ω) : sans UTF-8, la console
# Windows plante dans le fil de connexion.
for flux in (sys.stdout, sys.stderr):
    try:
        flux.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# config.ini est lu dans le dossier courant : on se place dans le dossier du projet
os.chdir(os.path.dirname(os.path.abspath(__file__)))

NOMS_OBJETS = [nom.strip() for nom in os.getenv("PORTE_OBJETS", "rasp_door,porte_magique").split(",") if nom.strip()]
PERIODE_ENVOI = 1.0   # secondes entre deux envois de l'état

objets = []           # objets AliotObj créés
_geste = ""
_action = ""
_verrou = threading.Lock()


def demarrer():
    """Lance la connexion des objets en arrière-plan. Retourne False si impossible."""
    try:
        from aliot.aliot_obj import AliotObj
    except ImportError:
        print("ALIOT : librairie absente (pip install aliot-py), tableau de bord désactivé.")
        return False

    for nom in NOMS_OBJETS:
        try:
            objet = AliotObj(nom)
        except Exception as erreur:
            print(f"ALIOT : objet « {nom} » ignoré ({erreur}).")
            continue
        _enregistrer_actions(objet)
        threading.Thread(target=objet.run, daemon=True).start()
        objets.append(objet)
        print(f"ALIOT : connexion de l'objet « {nom} »...")

    if objets:
        threading.Thread(target=_envoyer_en_continu, daemon=True).start()
    return bool(objets)


def objets_connectes():
    return [objet for objet in objets if objet.connected_to_alivecode]


def est_connecte():
    return bool(objets_connectes())


def resume_connexion():
    """Texte court pour l'écran, ex. « ALIOT 2/2 »."""
    return f"ALIOT {len(objets_connectes())}/{len(objets)}" if objets else "ALIOT -"


def signaler_geste(geste, action):
    """Appelée quand un geste déclenche une action : envoi immédiat aux tableaux de bord."""
    global _geste, _action
    with _verrou:
        _geste, _action = geste, action
    for objet in objets_connectes():
        objet.update_doc({"/doc/geste": geste, "/doc/action_geste": action})
        objet.update_component("historique", f"Geste : {geste} -> {action}")


def _etat_de_la_porte():
    etat = porte_utils.get_etat()
    distance = porte_utils.get_distance()
    with _verrou:
        geste, action = _geste, _action
    champs = {
        "/doc/actif": porte_utils.get_actif(),
        "/doc/etat": etat,
        "/doc/porte_ouverte": etat == "OUVERTE",
        "/doc/presence": porte_utils.get_presence(),
        "/doc/distance": distance if distance is not None else 0,
        "/doc/angle": porte_utils.get_angle() or 0,
        "/doc/ledV": porte_utils.get_led_verte(),
        "/doc/ledR": porte_utils.get_led_rouge(),
        "/doc/geste": geste,
        "/doc/action_geste": action,
    }
    lcd = porte_utils.get_lcd()
    if lcd is not None:
        champs["/doc/lcd"] = f"{lcd[0]} / {lcd[1]}" if lcd[1] else lcd[0]
    return champs


def _envoyer_en_continu():
    """Envoie l'état de la porte aux tableaux de bord chaque seconde."""
    while True:
        time.sleep(PERIODE_ENVOI)
        connectes = objets_connectes()
        if not connectes:
            continue
        champs = _etat_de_la_porte()
        for objet in connectes:
            try:
                objet.update_doc(champs)
                objet.update_component("led_stateV", champs["/doc/ledV"])
                objet.update_component("led_stateR", champs["/doc/ledR"])
                objet.update_component("distance", champs["/doc/distance"])
            except Exception as erreur:   # une coupure réseau ne doit pas arrêter la porte
                print(f"ALIOT : envoi impossible à « {objet.name} » ({erreur}).")


def _texte_recu(data, cle="message"):
    return data.get(cle, "") if isinstance(data, dict) else str(data or "")


def _vrai(valeur):
    return valeur in (True, "true", "True", 1, "1")


def _enregistrer_actions(objet):
    """Boutons des interfaces ALIVEcode (identifiants de iteration2.py et log.py)."""

    def action(action_id):
        return objet.on_action_recv(action_id=action_id)

    # --- Porte ---
    @action("ouvrir_porte")
    def ouvrir_porte(data):
        porte_utils.ouvrir(_texte_recu(data, "nom").strip()[:16] or "Tableau de bord")

    @action("fermer_porte")
    def fermer_porte(data):
        porte_utils.fermer()

    # --- Système ---
    @action("alterner_systeme")
    def alterner_systeme(valeur):
        porte_utils.set_systeme(_vrai(valeur))

    @action("activer_systeme")
    def activer_systeme(data):
        porte_utils.set_systeme(True)

    @action("desactiver_systeme")
    def desactiver_systeme(data):
        porte_utils.set_systeme(False)

    @action("verrouiller")
    def verrouiller(valeur):
        if _vrai(valeur):
            porte_utils.fermer()
        porte_utils.set_systeme(not _vrai(valeur))

    # --- LED ---
    @action("allumer_led_rouge")
    def allumer_led_rouge(data):
        porte_utils.regler_led_rouge(True)

    @action("allumer_led_verte")
    def allumer_led_verte(data):
        porte_utils.regler_led_verte(True)

    @action("allumer_leds")
    def allumer_leds(data):
        porte_utils.regler_led_rouge(True)
        porte_utils.regler_led_verte(True)

    @action("eteindre_leds")
    def eteindre_leds(data):
        porte_utils.eteindre_leds()

    @action("leds_automatiques")
    def leds_automatiques(data):
        porte_utils.leds_automatiques()

    # --- Buzzer ---
    @action("tester_buzzer")
    def tester_buzzer(data):
        porte_utils.activer_buzzer(True)
        porte_utils.buzzer(450)

    @action("eteindre_buzzer")
    def eteindre_buzzer(data):
        porte_utils.buzzer(0)
        porte_utils.activer_buzzer(False)

    @action("couper_alarme")
    def couper_alarme(data):
        porte_utils.buzzer(0)
        porte_utils.activer_buzzer(False)

    # --- Écran LCD ---
    @action("afficher_lcd")
    def afficher_lcd(data):
        texte = _texte_recu(data)
        ligne1, separateur, ligne2 = texte.partition("|")
        if not separateur and len(ligne1) > 16:
            ligne1, ligne2 = ligne1[:16], ligne1[16:32]
        porte_utils.afficher_lcd(ligne1, ligne2)
