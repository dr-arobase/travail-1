import serial
import time
import threading
import math

# Définition du port série et de la vitesse de communication
ser = serial.Serial('COM3', 9600)  # Remplace 'COM5' par ton port série si besoin


_led_state = False



def set_led(state):
    global _led_state
    if state:
        ser.write(b't')  # Envoie 't' pour allumer la LED
        _led_state = True
    else:
        ser.write(b'f')  # Envoie 'f' pour éteindre la LED
        _led_state = False

def toggle_led():
    if _led_state:
        set_led(False)
    else:
        set_led(True)

def get_led_state():
    return _led_state

def read_data():
    try:
        data = ser.readline().decode().strip()
        if not data:
            return None, None, None
            
        parts = data.split(':')
        if len(parts) != 3:
            return None, None, None
            import serial
import time
import threading
import math

# Définition du port série et de la vitesse de communication
ser = serial.Serial('COM3', 9600)  # Remplace 'COM5' par ton port série si besoin

luminosity = None
temperature = None
humidity = None
_led_state = False

def get_temperature_and_humidity():
    if temperature is None or humidity is None:
        return None, None
    if math.isnan(temperature) or math.isnan(humidity):
        return None, None
    return temperature, humidity
    
def get_luminosity():
    return luminosity

def set_led(state):
    global _led_state
    if state:
        ser.write(b't')  # Envoie 't' pour allumer la LED
        _led_state = True
    else:
        ser.write(b'f')  # Envoie 'f' pour éteindre la LED
        _led_state = False

def toggle_led():
    if _led_state:
        set_led(False)
    else:
        set_led(True)

def get_led_state():
    return _led_state

def read_data():
    try:
        data = ser.readline().decode().strip()
        if not data:
            return None, None, None
            
        parts = data.split(':')
        if len(parts) != 3:
            return None, None, None
            
        temp_val, hum_val, lum_val = parts
        
        # Inversion de la luminosité brute (si l'Arduino envoie une valeur brute de 0 à 1023)
        # Plus la valeur brute lue est basse, plus il y a de lumière -> on convertit en pourcentage inversé (0 à 100%)
        lum_brute = float(lum_val)
        lum_pourcent = 100 - ((lum_brute * 100) / 1023.0)
        
        # Sécurité pour garder le pourcentage entre 0 et 100
        lum_pourcent = round(max(0.0, min(100.0, lum_pourcent)), 1)
        
        return float(temp_val), float(hum_val), lum_pourcent
        
    except Exception as e:
        return None, None, None

def read_from_serial():
    global temperature, humidity, luminosity
    try:
        pass

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        ser.close()

try:
    t = threading.Thread(target=read_from_serial, daemon=True)
    t.start()
except KeyboardInterrupt:
    print("Exiting...")
def read_from_serial():
    global _led_state
    try:
        pass

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        ser.close()

try:
    t = threading.Thread(target=read_from_serial, daemon=True)
    t.start()
except KeyboardInterrupt:
    print("Exiting...")