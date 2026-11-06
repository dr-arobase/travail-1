# Documentation: https://alivecode.ca/docs/aliot
# Itération 2 : Porte magique
import os

# Se placer dans le dossier du script pour trouver config.ini
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import time
from datetime import datetime

import porte_utils
from aliot.aliot_obj import AliotObj

# Attente pour bien établir la communication avec l'Arduino
time.sleep(5)

# Objet utilisé : "porte_magique" (Massyle) ou "rasp_door" (Ernst)
OBJET = os.getenv("PORTE_OBJET", "porte_magique")

# Création de l'objet à partir du fichier de configuration
porte = AliotObj(OBJET)

# Seuil de refus d'affilée avant de déclencher l'alarme
SEUIL_ALARME = 3


# ---------- Base de données : création des champs ----------
def creer_base_de_donnees():
    # On garde les données déjà enregistrées (get_doc) et on crée celles qui manquent
    if lire("/doc/autorises") is None:
        porte.update_doc({"/doc/autorises": ["Massyle"]})
    if lire("/doc/stats") is None:
        porte.update_doc({"/doc/stats": stats_vides()})
    if lire("/doc/historique") is None:
        porte.update_doc({"/doc/historique": []})

    porte.update_doc({
        "/doc/ledV": False,
        "/doc/ledR": False,
        "/doc/buzzer": 0,
        "/doc/refus_suite": 0,
    })


def stats_vides():
    return {
        "ouvertures": 0,
        "ouvertures_jour": 0,
        "refus": 0,
        "presences": 0,
        "taux_acces": 100,
        "jour": datetime.now().strftime("%Y-%m-%d"),
    }


# ---------- Base de données : lecture ----------
def lire(champ):
    try:
        return porte.get_doc(champ)
    except Exception:
        return None


def est_autorise(nom):
    autorises = lire("/doc/autorises") or []
    return nom.lower() in [a.lower() for a in autorises]


# ---------- Fonctionnalités : statistiques et historique ----------
def ajouter_historique(texte):
    historique = lire("/doc/historique") or []
    historique.insert(0, f"{datetime.now().strftime('%H:%M:%S')} {texte}")
    porte.update_doc({"/doc/historique": historique[:10]})
    porte.update_component("historique", texte)


def compter(cle):
    stats = lire("/doc/stats") or stats_vides()

    # Nouveau jour : on remet le compteur du jour à zéro
    aujourd_hui = datetime.now().strftime("%Y-%m-%d")
    if stats.get("jour") != aujourd_hui:
        stats["jour"] = aujourd_hui
        stats["ouvertures_jour"] = 0

    stats[cle] = stats.get(cle, 0) + 1
    if cle == "ouvertures":
        stats["ouvertures_jour"] = stats.get("ouvertures_jour", 0) + 1

    total = stats.get("ouvertures", 0) + stats.get("refus", 0)
    stats["taux_acces"] = round(stats.get("ouvertures", 0) / total * 100) if total else 100

    porte.update_doc({"/doc/stats": stats})

    # Vérification que la modification est bien enregistrée
    print(f"Vérification {cle} : {lire('/doc/stats/' + cle)}")


def acces_autorise(nom):
    compter("ouvertures")
    porte_utils.buzzer(0)
    porte.update_doc({
        "/doc/ledV": True,
        "/doc/ledR": False,
        "/doc/buzzer": 0,
        "/doc/refus_suite": 0,
        "/doc/derniere_visite": {"nom": nom, "heure": datetime.now().strftime("%H:%M:%S")},
    })
    ajouter_historique(f"{nom} - ouverture")


def acces_refuse(raison):
    compter("refus")
    refus_suite = (lire("/doc/refus_suite") or 0) + 1
    if refus_suite >= SEUIL_ALARME:
        porte_utils.buzzer(450)
    porte.update_doc({
        "/doc/ledV": False,
        "/doc/ledR": True,
        "/doc/refus_suite": refus_suite,
        "/doc/buzzer": 450 if refus_suite >= SEUIL_ALARME else 0,
    })
    ajouter_historique(f"refus - {raison}")


def traiter_evenement(evenement):
    print(f"Événement : {evenement}")

    if evenement.startswith("PORTE_OUVERTE"):
        nom = evenement.partition(":")[2] or "Ami"
        acces_autorise(nom)
    elif evenement == "ACCES_REFUSE":
        acces_refuse("visage inconnu")
    elif evenement == "PRESENCE_DETECTEE":
        compter("presences")
        ajouter_historique("présence détectée")
    elif evenement == "PORTE_FERMEE":
        porte.update_doc({"/doc/ledV": False})
        ajouter_historique("porte fermée")
    elif evenement == "SYSTEME_ON":
        ajouter_historique("système activé")
    elif evenement == "SYSTEME_OFF":
        ajouter_historique("système désactivé")
    elif evenement == "BOUTON":
        ajouter_historique("bouton appuyé")
    elif evenement == "LCD_MESSAGE":
        print("Message affiché sur le LCD")


# ---------- LED : même état que les LED de l'Arduino ----------
def etat_des_leds():
    return {
        "/doc/ledV": porte_utils.get_led_verte(),   # LED verte allumée ?
        "/doc/ledR": porte_utils.get_led_rouge(),   # LED rouge allumée ?
    }


def dernier_evenement():
    evenements = porte_utils.get_evenements()
    if not evenements:
        return ""
    for evenement in evenements:
        traiter_evenement(evenement)
    return evenements[-1]


def start():
    creer_base_de_donnees()

    while True:
        try:
            # Obtenir les données de l'Arduino
            actif = porte_utils.get_actif()
            etat = porte_utils.get_etat()
            presence = porte_utils.get_presence()
            distance = porte_utils.get_distance()
            angle = porte_utils.get_angle()

            # Affichage
            print(f"Actif: {actif} | Etat: {etat}")
            print(f"Presence: {presence} | Distance: {distance} cm | Angle: {angle}")
            print(f"LED verte: {porte_utils.get_led_verte()} | LED rouge: {porte_utils.get_led_rouge()}")

            # Envoi des données au serveur ALIVEcode
            fields = {
                "/doc/actif": actif,
                "/doc/etat": etat,
                "/doc/porte_ouverte": etat == "OUVERTE",
                "/doc/presence": presence,
                "/doc/distance": distance if distance is not None else 0,
                "/doc/angle": angle if angle is not None else 0,
                "/doc/evenement": dernier_evenement(),
            }
            fields.update(etat_des_leds())

            # Texte réellement affiché sur le LCD de l'Arduino
            lcd = porte_utils.get_lcd()
            if lcd is not None:
                fields["/doc/lcd"] = f"{lcd[0]} / {lcd[1]}" if lcd[1] else lcd[0]
            porte.update_doc(fields)

            # Mise à jour des LED de l'interface par leur identifiant
            porte.update_component("led_stateV", fields["/doc/ledV"])
            porte.update_component("led_stateR", fields["/doc/ledR"])

            # Attente de 1 seconde
            time.sleep(1)
        except KeyboardInterrupt:
            break


# Procédures appelées quand un bouton de l'interface envoie une action
@porte.on_action_recv(action_id="ouvrir_porte")
def ouvrir_porte(data):
    if isinstance(data, dict):
        nom = data.get("nom", "Massyle")
    else:
        nom = str(data or "").strip() or "Massyle"
    if est_autorise(nom):
        porte_utils.ouvrir(nom)
    else:
        porte_utils.refuser()
        acces_refuse(f"{nom} non autorisé")


@porte.on_action_recv(action_id="fermer_porte")
def fermer_porte(data):
    porte_utils.fermer()


@porte.on_action_recv(action_id="ajouter_autorise")
def ajouter_autorise(data):
    nom = data.get("nom", "") if isinstance(data, dict) else str(data or "")
    nom = nom.strip()[:16]
    autorises = lire("/doc/autorises") or []
    if nom and nom not in autorises:
        autorises.append(nom)
        porte.update_doc({"/doc/autorises": autorises})
        ajouter_historique(f"{nom} ajouté aux autorisés")


@porte.on_action_recv(action_id="retirer_autorise")
def retirer_autorise(data):
    nom = data.get("nom", "") if isinstance(data, dict) else str(data or "")
    autorises = [a for a in (lire("/doc/autorises") or []) if a.lower() != nom.strip().lower()]
    porte.update_doc({"/doc/autorises": autorises})
    ajouter_historique(f"{nom.strip()} retiré des autorisés")


@porte.on_action_recv(action_id="couper_alarme")
def couper_alarme(data):
    porte_utils.buzzer(0)
    porte.update_doc({"/doc/buzzer": 0, "/doc/ledR": False, "/doc/refus_suite": 0})
    ajouter_historique("alarme coupée")


@porte.on_action_recv(action_id="reset_stats")
def reset_stats(data):
    porte.update_doc({"/doc/stats": stats_vides()})
    ajouter_historique("statistiques réinitialisées")


# Le composant « Invite d'un objet IoT » envoie le texte écrit dans l'interface
@porte.on_action_recv(action_id="afficher_lcd")
def afficher_lcd(data):
    texte = data.get("message", "") if isinstance(data, dict) else str(data or "")
    ligne1, _, ligne2 = texte.partition("|")
    if not ligne2 and len(ligne1) > 16:
        ligne1, ligne2 = ligne1[:16], ligne1[16:32]
    porte_utils.afficher_lcd(ligne1, ligne2)
    ajouter_historique(f"LCD : {texte}")


# L'interrupteur « Verrouillage » envoie son état : True (verrouillé) ou False
@porte.on_action_recv(action_id="verrouiller")
def verrouiller(value):
    verrouille = value in (True, "true", "True", 1, "1")
    if verrouille:
        porte_utils.fermer()
    porte_utils.set_systeme(not verrouille)
    porte.update_doc({"/doc/verrouille": verrouille})
    ajouter_historique("porte verrouillée" if verrouille else "porte déverrouillée")


# L'interrupteur envoie directement son état : True (activé) ou False (désactivé)
@porte.on_action_recv(action_id="alterner_systeme")
def alterner_systeme(value):
    porte_utils.set_systeme(value)


@porte.on_action_recv(action_id="activer_systeme")
def activer_systeme(data):
    porte_utils.set_systeme(True)


@porte.on_action_recv(action_id="desactiver_systeme")
def desactiver_systeme(data):
    porte_utils.set_systeme(False)


porte.on_start(callback=start)

# Connection de l'objet au serveur ALIVEcode
porte.run()
