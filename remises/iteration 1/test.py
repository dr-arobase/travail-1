import threading
import time
from datetime import datetime
from pathlib import Path

import serial
import serial.tools.list_ports

# La caméra n'existe que sur le Raspberry Pi : sur un PC, le reste du programme marche quand même
try:
    from picamera2 import Picamera2, Preview
except ImportError:
    Picamera2 = None

DOSSIER = Path(__file__).resolve().parent
DOSSIER_PHOTOS = DOSSIER / "photos"
DOSSIER_VIDEOS = DOSSIER / "videos"


# ===================== ARDUINO =====================

def trouver_port_arduino():
    """Détecte automatiquement le port de l'Arduino (COM6 sur Windows, /dev/ttyACM0 sur le Pi)."""
    mots_cles = ("arduino", "ch340", "usb-serial", "usb serial", "ttyacm", "ttyusb")
    for port in serial.tools.list_ports.comports():
        texte = f"{port.device} {port.description}".lower()
        if any(mot in texte for mot in mots_cles):
            return port.device
    return None

def lire_arduino(ser, actif):
    """Affiche en continu les messages de l'Arduino et prend une photo quand la porte s'ouvre."""
    while actif.is_set():
        try:
            ligne = ser.readline().decode('utf-8', errors='ignore').strip()
        except serial.SerialException:
            print("\nConnexion avec l'Arduino perdue.")
            actif.clear()
            break
        if not ligne:
            continue
        print(f"\n[Arduino] {ligne}")

        if ligne.startswith("Porte ouverte"):
            prendre_photo("visiteur")
        elif ligne.startswith("Mouvement"):
            prendre_photo("mouvement")


# ===================== CAMERA =====================

picam2 = None
verrou_camera = threading.Lock()  # la caméra est utilisée par le menu ET par les photos automatiques

def demarrer_camera():
    global picam2
    if Picamera2 is None:
        print("Caméra : picamera2 absent (normal sur un PC) -> options caméra désactivées.")
        return
    try:
        picam2 = Picamera2()
        picam2.configure(picam2.create_preview_configuration(main={"size": (1280, 720)}))
        picam2.start()
        time.sleep(2)  # Pause pour laisser la caméra ajuster la lumière
        print("Caméra prête.")
    except Exception as erreur:
        print(f"Caméra introuvable ({erreur}) -> options caméra désactivées.")
        picam2 = None

def camera_disponible():
    if picam2 is None:
        print("[!] Pas de caméra disponible.")
        return False
    return True

def prendre_photo(prefixe="photo"):
    if picam2 is None:
        return
    DOSSIER_PHOTOS.mkdir(exist_ok=True)
    fichier = DOSSIER_PHOTOS / f"{prefixe}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    with verrou_camera:
        picam2.capture_file(str(fichier))
    print(f"-> Photo enregistrée : {fichier.name}")

def apercu_direct():
    if not camera_disponible():
        return
    print("\n-> Ouverture de l'aperçu en direct.")
    print("   (Appuyez sur 'Entrée' dans ce terminal pour fermer l'aperçu)")
    with verrou_camera:
        picam2.stop()
        try:
            picam2.start_preview(Preview.QTGL)
        except Exception:
            picam2.start_preview(Preview.QT)  # si l'accélération graphique n'est pas disponible
        picam2.start()
    input()
    with verrou_camera:
        picam2.stop()
        picam2.stop_preview()
        picam2.start()
    print("-> Aperçu fermé.")

def enregistrer_video(duree=5):
    if not camera_disponible():
        return
    DOSSIER_VIDEOS.mkdir(exist_ok=True)
    fichier = DOSSIER_VIDEOS / f"video_{datetime.now():%Y%m%d_%H%M%S}.mp4"
    print(f"\n-> Enregistrement de la vidéo ({duree} secondes)...")
    with verrou_camera:
        picam2.stop()
        picam2.configure(picam2.create_video_configuration(main={"size": (1280, 720)}))
        picam2.start_and_record_video(str(fichier), duration=duree)
        # Retour à la configuration normale pour les photos
        picam2.stop()
        picam2.configure(picam2.create_preview_configuration(main={"size": (1280, 720)}))
        picam2.start()
    print(f"-> Succès ! Vidéo enregistrée : {fichier.name}")


# ===================== PROGRAMME PRINCIPAL =====================

demarrer_camera()

ser = None
actif = threading.Event()
port_com = trouver_port_arduino()

if not port_com:
    print("Arduino : aucun Arduino trouvé -> options de la porte désactivées.")
else:
    try:
        # Ouverture de la liaison série à 9600 bauds
        ser = serial.Serial(port_com, 9600, timeout=1)
        print(f"Arduino détecté sur le port : {port_com}")
        print("Démarrage de la porte (environ 4 secondes)...")
        time.sleep(2)  # Temps de réinitialisation de la carte

        # Lecture des messages de l'Arduino en arrière-plan
        actif.set()
        threading.Thread(target=lire_arduino, args=(ser, actif), daemon=True).start()
        time.sleep(2)  # Le temps que l'Arduino termine son démarrage
    except serial.SerialException:
        print("Erreur : le port est occupé. Fermez le Moniteur série d'Arduino IDE et réessayez.")
        ser = None

def envoyer(commande):
    if ser is None or not actif.is_set():
        print("[!] Pas d'Arduino connecté.")
        return
    ser.write((commande + "\n").encode('utf-8'))
    time.sleep(0.3)  # Laisse le temps à la réponse de s'afficher

# Boucle du menu principal
while True:
    print("\n" + "=" * 40)
    print("     PORTE INTELLIGENTE + CAMERA")
    print("=" * 40)
    print("1. Me voir en direct (Aperçu vidéo)")
    print("2. Prendre une photo")
    print("3. Enregistrer une vidéo (5 secondes)")
    print("4. Ouvrir la porte")
    print("5. Fermer la porte")
    print("6. État de la porte (et distance)")
    print("7. Quitter")
    print("=" * 40)
    print("(Photo automatique quand la porte s'ouvre ou qu'un mouvement est détecté)")

    try:
        choix = input("Faites votre choix (1 à 7) : ").strip()
    except (KeyboardInterrupt, EOFError):
        choix = '7'  # Ctrl + C ferme proprement le programme

    if choix == '1':
        apercu_direct()
    elif choix == '2':
        prendre_photo("photo")
    elif choix == '3':
        enregistrer_video(5)
    elif choix == '4':
        envoyer("OUVRIR")
    elif choix == '5':
        envoyer("FERMER")
    elif choix == '6':
        envoyer("ETAT")
    elif choix == '7':
        print("\nFermeture du programme. Au revoir !")
        break
    else:
        print("\n[!] Choix invalide, veuillez entrer un chiffre de 1 à 7.")

actif.clear()
if ser is not None:
    ser.close()
if picam2 is not None:
    picam2.close()
