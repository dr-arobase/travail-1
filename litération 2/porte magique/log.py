import os

# Se placer dans le dossier du script pour trouver config.ini
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from aliot.aliot_obj import AliotObj
import time

import porte_utils

time.sleep(5)

# Objet utilisé : "porte_magique" (Massyle) ou "rasp_door" (Ernst)
capteur_porte = AliotObj(os.getenv("PORTE_OBJET", "porte_magique"))


def start():
    while True:
        try:
            etat = porte_utils.get_etat()
            distance = porte_utils.get_distance()
            angle = porte_utils.get_angle()
            presence = porte_utils.get_presence()

            print(
                f"État: {etat} | "
                f"Distance: {distance} cm | "
                f"Angle: {angle}° | "
                f"Présence: {'OUI' if presence else 'NON'}"
            )

            if distance is not None:
                capteur_porte.update_component("distance", distance)
            if angle is not None:
                capteur_porte.update_component("angle", angle)
            capteur_porte.update_component("led_stateV", porte_utils.get_led_verte())
            capteur_porte.update_component("led_stateR", porte_utils.get_led_rouge())
            if etat == "REFUSEE":
                capteur_porte.update_component("Mybuzzer", 450)
            else:
                capteur_porte.update_component("Mybuzzer", 0)

            time.sleep(1)
        except KeyboardInterrupt:
            break


capteur_porte.on_start(callback=start)
capteur_porte.run()
