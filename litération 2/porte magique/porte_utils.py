import os
import threading
import time

try:
    import serial
    from serial import SerialException
    import serial.tools.list_ports
except ImportError as error:
    raise RuntimeError(
        "pyserial est requis. Installez-le avec : python -m pip install pyserial"
    ) from error


_lock = threading.Lock()
_serial = None
_lecture_active = threading.Event()
_actif = False
_etat = "VEILLE"
_presence = False
_distance = None
_angle = None
_led_r = False
_led_v = False
_lcd = None
_evenements = []


def _trouver_port():
    port_force = os.getenv("PORTE_PORT")
    if port_force:
        return port_force

    mots_cles = ("arduino", "ch340", "usb-serial", "usb serial", "ttyacm", "ttyusb")
    for port in serial.tools.list_ports.comports():
        texte = f"{port.device} {port.description}".lower()
        if any(mot in texte for mot in mots_cles):
            return port.device
    return None


def _connecter():
    global _serial

    port = _trouver_port()
    if port is None:
        print("Arduino : aucun port série détecté. Branchez la carte puis relancez.")
        return False

    try:
        _serial = serial.Serial(port, 9600, timeout=1)
    except SerialException as error:
        print(f"Arduino : impossible d'ouvrir {port} ({error}).")
        return False

    time.sleep(2)
    _lecture_active.set()
    threading.Thread(target=_read_from_serial, daemon=True).start()
    print(f"Arduino connecté sur {port}.")
    return True


def _envoyer(message):
    with _lock:
        if _serial is None or not _lecture_active.is_set():
            print(f"Arduino : commande ignorée, aucune connexion ({message.strip()}).")
            return False
        try:
            _serial.write(message.encode("utf-8"))
            _serial.flush()
        except SerialException as error:
            print(f"Arduino : échec de la commande ({error}).")
            return False
    return True


def ouvrir(nom="Ami"):
    return _envoyer(f"OPEN:{nom}\n")


def fermer():
    return _envoyer("CLOSE\n")


def refuser():
    return _envoyer("DENY\n")


def basculer_systeme():
    return _envoyer("TOGGLE\n")


def afficher_lcd(ligne1, ligne2=""):
    """Affiche deux lignes (16 caractères max, sans accents) sur l'écran LCD."""
    import unicodedata

    def nettoyer(texte):
        texte = unicodedata.normalize("NFKD", str(texte))
        texte = texte.encode("ascii", "ignore").decode("ascii")
        return texte.replace("|", " ")[:16]

    return _envoyer(f"MSG:{nettoyer(ligne1)}|{nettoyer(ligne2)}\n")


def buzzer(frequence):
    """Fait sonner le buzzer (0 = silence)."""
    return _envoyer(f"BUZZ:{int(frequence)}\n")


def set_systeme(state):
    if get_actif() != bool(state):
        basculer_systeme()


def get_actif():
    with _lock:
        return _actif


def get_etat():
    with _lock:
        return _etat


def get_presence():
    with _lock:
        return _presence


def get_distance():
    with _lock:
        return _distance


def get_angle():
    with _lock:
        return _angle


def get_led_rouge():
    with _lock:
        return _led_r


def get_led_verte():
    with _lock:
        return _led_v


def get_lcd():
    """Texte affiché sur le LCD : (ligne1, ligne2) ou None si inconnu."""
    with _lock:
        return _lcd


def get_evenements():
    """Retourne les nouveaux événements de l'Arduino et vide la liste."""
    global _evenements

    with _lock:
        evenements = _evenements
        _evenements = []
    return evenements


def _read_value(parts, names):
    for part in parts:
        key, separator, value = part.partition("=")
        if separator and key.strip().lower() in names:
            return value.strip()
    return None


def _read_data():
    line = _serial.readline().decode("utf-8", errors="replace").strip()
    if not line:
        return

    # Contenu de l'écran : LCD:Bienvenue|Massyle
    if line.startswith("LCD:"):
        global _lcd
        ligne1, _, ligne2 = line[4:].partition("|")
        with _lock:
            _lcd = (ligne1.strip(), ligne2.strip())
        return

    # Événement : EVT:PORTE_OUVERTE:Massyle
    if line.startswith("EVT:"):
        with _lock:
            _evenements.append(line[4:])
        return

    # État : STATUS:actif=1,etat=VEILLE,presence=0,distance=120,angle=0
    if not line.startswith("STATUS:"):
        return

    parts = [part.strip() for part in line[7:].split(",")]
    actif = _read_value(parts, {"actif"})
    etat = _read_value(parts, {"etat"})
    presence = _read_value(parts, {"presence"})
    distance = _read_value(parts, {"distance"})
    angle = _read_value(parts, {"angle"})
    led_r = _read_value(parts, {"ledr"})
    led_v = _read_value(parts, {"ledv"})

    with _lock:
        global _actif, _etat, _presence, _distance, _angle, _led_r, _led_v
        if actif is not None:
            _actif = actif == "1"
        if etat is not None:
            _etat = etat
        if presence is not None:
            _presence = presence == "1"
        if distance is not None:
            _distance = int(distance)
        if angle is not None:
            _angle = int(angle)
        if led_r is not None:
            _led_r = led_r == "1"
        if led_v is not None:
            _led_v = led_v == "1"


def _read_from_serial():
    while _lecture_active.is_set():
        try:
            _read_data()
        except (SerialException, UnicodeError, ValueError):
            time.sleep(1)


_connecter()
