import os

# Se placer dans le dossier du script pour trouver config.ini
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from aliot.aliot_obj import AliotObj
import time

import porte_utils

time.sleep(5)

# Objet actif dans ALIOT; PORTE_OBJET permet de sélectionner un autre objet.
capteur_porte = AliotObj(os.getenv("PORTE_OBJET", "rasp_door"))


_presence_precedente = None


def mettre_a_jour_sorties_presence(presence):
    """Active les sorties à la détection et restaure le mode normal au départ."""
    global _presence_precedente
    if presence == _presence_precedente:
        return

    if presence:
        commandes = (
            (porte_utils.regler_led_verte, (True,)),
            (porte_utils.activer_buzzer, (True,)),
            (porte_utils.buzzer, (450,)),
        )
        description = "présence détectée : LED verte et buzzer activés"
    else:
        commandes = (
            (porte_utils.buzzer, (0,)),
            (porte_utils.activer_buzzer, (False,)),
            (porte_utils.leds_automatiques, ()),
        )
        description = "présence terminée : buzzer coupé, LED en mode automatique"

    resultats = [commande(*arguments) for commande, arguments in commandes]
    if all(resultats):
        _presence_precedente = presence
        print(description)
    else:
        print(f"Impossible d'appliquer toutes les sorties : {description}.")


def executer_action(description, commande):
    if not commande():
        print(f"Arduino : impossible d'exécuter « {description} ».")
        return
    print(description)


def start():
    while True:
        try:
            actif = porte_utils.get_actif()
            etat = porte_utils.get_etat()
            distance = porte_utils.get_distance()
            angle = porte_utils.get_angle()
            presence = porte_utils.get_presence()
            mettre_a_jour_sorties_presence(presence)
    

            print(
                f"État: {etat} | "
                f"Distance: {distance} cm | "
                f"Angle: {angle}° | "
                f"Présence: {'OUI' if presence else 'NON'}"
            )

            capteur_porte.update_doc({"/doc/actif": actif})
            if distance is not None:
                capteur_porte.update_component("distance", distance)
            if angle is not None:
                capteur_porte.update_component("angle", angle)
            capteur_porte.update_component("led_stateV", porte_utils.get_led_verte())
            capteur_porte.update_component("led_stateR", porte_utils.get_led_rouge())
            if presence or etat == "REFUSEE":
                capteur_porte.update_component("Mybuzzer", 450)
            else:
                capteur_porte.update_component("Mybuzzer", 0)

            lcd = porte_utils.get_lcd()
            fields = {}
            if lcd is not None:
                fields["/doc/lcd"] = f"{lcd[0]} / {lcd[1]}" if lcd[1] else lcd[0]
            if fields:
                capteur_porte.update_doc(fields)

            time.sleep(1)
        except KeyboardInterrupt:
            break


@capteur_porte.on_action_recv(action_id="fermer_porte")
def fermer_porte(data):
    executer_action("fermeture de la porte demandée depuis l'interface", porte_utils.fermer)


@capteur_porte.on_action_recv(action_id="allumer_led_verte")
def allumer_led_verte(data):
    executer_action("LED verte allumée en mode manuel", lambda: porte_utils.regler_led_verte(True))


@capteur_porte.on_action_recv(action_id="allumer_led_rouge")
def allumer_led_rouge(data):
    executer_action("LED rouge allumée en mode manuel", lambda: porte_utils.regler_led_rouge(True))


@capteur_porte.on_action_recv(action_id="allumer_leds")
def allumer_leds(data):
    verte = porte_utils.regler_led_verte(True)
    rouge = porte_utils.regler_led_rouge(True)
    if not verte or not rouge:
        print("Arduino : impossible d'allumer les deux LED.")
        return
    print("LED verte et LED rouge allumées en mode manuel")


@capteur_porte.on_action_recv(action_id="eteindre_leds")
def eteindre_leds(data):
    executer_action("LED éteintes en mode manuel", porte_utils.eteindre_leds)


@capteur_porte.on_action_recv(action_id="leds_automatiques")
def leds_automatiques(data):
    executer_action("contrôle automatique des LED réactivé", porte_utils.leds_automatiques)


@capteur_porte.on_action_recv(action_id="tester_buzzer")
def tester_buzzer(data):
    actif = porte_utils.activer_buzzer(True)
    son = porte_utils.buzzer(450)
    if not actif or not son:
        print("Arduino : impossible d'activer le buzzer.")
        return
    print("Buzzer activé depuis l'interface")


@capteur_porte.on_action_recv(action_id="eteindre_buzzer")
def eteindre_buzzer(data):
    silence = porte_utils.buzzer(0)
    inactif = porte_utils.activer_buzzer(False)
    if not silence or not inactif:
        print("Arduino : impossible d'éteindre le buzzer.")
        return
    print("Buzzer éteint depuis l'interface")


@capteur_porte.on_action_recv(action_id="afficher_lcd")
def afficher_lcd(data):
    texte = data.get("message", "") if isinstance(data, dict) else str(data or "")
    ligne1, separateur, ligne2 = texte.partition("|")
    if not separateur and len(ligne1) > 16:
        ligne1, ligne2 = ligne1[:16], ligne1[16:32]

    executer_action(
        "message affiché sur le LCD",
        lambda: porte_utils.afficher_lcd(ligne1, ligne2),
    )


capteur_porte.on_start(callback=start)
capteur_porte.run()
