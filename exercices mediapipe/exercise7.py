"""
Exercice 7 - Detection de personnes, separation personne / peau, et son

1. Selfie Segmentation : masque de TOUTES les personnes a l'image.
2. Face Mesh (468 points par visage) : trouve chaque visage et donne la
   position exacte du front et des joues.
3. La peau est mesuree uniquement sur le front et les joues (pas les yeux,
   la bouche, la barbe ou les cheveux) apres une balance des blancs.
   Mesure du teint : ITA (Individual Typology Angle, utilise en dermatologie).
4. Chaque personne est suivie d'une image a l'autre ; son teint est la
   mediane des dernieres mesures (stable, ne clignote pas).
5. Son : peau claire -> o.mp3, peau foncee -> x.mp3.
   Le son change A TOUT MOMENT : quand une personne arrive, ou quand le teint
   detecte d'une personne change, le son en cours est coupe et le bon son
   est joue.

Touche : q / Echap = quitter.
"""

import ctypes
import os
import shutil
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
import mediapipe.python.solution_base as mp_solution_base
from PIL import Image, ImageDraw, ImageFont

# Ecran a 150 % : sans ceci, Windows agrandit la fenetre OpenCV comme une
# photo et l'image devient floue. Ici, 1 pixel camera = 1 pixel ecran.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    pass


def fix_mediapipe_accent_path():
    """MediaPipe (C++) ne lit pas les chemins avec accents ("Collège").
    On copie ses modeles une seule fois dans un dossier sans accent
    (%LOCALAPPDATA%\\mediapipe_ascii) et on le redirige vers ce dossier."""
    package_dir = Path(mp.__file__).resolve().parent
    if str(package_dir).isascii():
        return
    ascii_root = Path(os.environ.get("LOCALAPPDATA", "C:/")) / "mediapipe_ascii"
    target = ascii_root / "mediapipe" / "modules"
    if not (target / "face_landmark").exists():
        print("Copie des modeles MediaPipe vers", target, "...")
        shutil.copytree(package_dir / "modules", target, dirs_exist_ok=True)
    mp_solution_base.__file__ = str(
        ascii_root / "mediapipe" / "python" / "solution_base.py"
    )


fix_mediapipe_accent_path()

WINDOW = "Exercice 7"
FONT = cv2.FONT_HERSHEY_SIMPLEX

segmenter = mp.solutions.selfie_segmentation.SelfieSegmentation(
    model_selection=1
)
face_mesh = mp.solutions.face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=5,
    refine_landmarks=False,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

# Deuxieme detecteur (longue portee) pour les visages que Face Mesh rate
# (personne loin, lunettes, visage de cote)
face_detector = mp.solutions.face_detection.FaceDetection(
    model_selection=1, min_detection_confidence=0.35,   # longue portee
)
face_detector_near = mp.solutions.face_detection.FaceDetection(
    model_selection=0, min_detection_confidence=0.35,   # courte portee
)

# Couleurs (BGR) des contours de chaque personne
PERSON_COLORS = [
    (255, 120, 0), (0, 200, 0), (200, 0, 200), (0, 200, 255), (255, 255, 0),
]
MIN_PERSON_AREA = 2500   # pixels min (petit : personnes loin aussi)
KERNEL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

# Points Face Mesh ou la peau est mesuree : front (3) + joues (4)
SKIN_LANDMARKS = [151, 108, 337, 50, 280, 205, 425]

# --- Teint : echelle de Fitzpatrick (types I a VI) -------------------------
# 1) luminosite de la peau corrigee par le mur derriere (annule l'exposition
#    automatique de la camera), 2) ITA = angle (luminosite, teinte b*),
# 3) ITA -> type de peau avec les seuils standards :
#    I > 55   II 41..55   III 28..41   IV 10..28   V -30..10   VI < -30
# Types I, II, III  -> GROUP_NAMES[1] -> o.mp3
# Types IV, V, VI   -> GROUP_NAMES[2] -> x.mp3
FITZPATRICK = [(55, 1), (41, 2), (28, 3), (10, 4), (-30, 5)]
TYPE_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI"}
WALL_REFLECTANCE = 0.9  # mur blanc ~ 0.9 (baisser si le mur est gris/beige)
MAX_PITCH = 0.70        # tete plus baissee que ca : pas de mesure
MAX_YAW = 0.25          # tete plus tournee que ca : pas de mesure
SKIN_B_MIN = 12         # b* minimum de la peau (webcam aux couleurs ternes)
HYSTERESIS = 3          # degres d'ITA a depasser pour changer de groupe
USE_COMPARISON = False  # True : forcer la difference entre 2 personnes
ITA_HISTORY = 15       # nombre de mesures gardees par personne
CONFIRM_FRAMES = 6     # images avant de decider le teint d'une nouvelle personne
LOST_FRAMES = 20       # une personne absente 20 images est oubliee
WARMUP_FRAMES = 60     # ~3 s : la camera regle son exposition, on ne mesure pas
# Plusieurs personnes : on les COMPARE entre elles (meme camera, meme
# eclairage). Si l'une est au moins 1.6x plus lumineuse que l'autre,
# la plus claire -> o.mp3 et la plus foncee -> x.mp3.
RELATIVE_GAP = 30     # degres d'ITA (si USE_COMPARISON = True)

# --- Sons ------------------------------------------------------------------
SOUND_DIR = Path(__file__).resolve().parents[2]   # dossier "Literation 3"
SOUNDS = {1: SOUND_DIR / "o.mp3", 2: SOUND_DIR / "x.mp3"}
# >>> Texte affiche au-dessus de chaque personne (accents permis) <<<
GROUP_NAMES = {1: "personne non suspecte", 2: "Personne suspecte"}
# Correction en direct : CLIQUE sur une personne pour inverser
# peau claire <-> peau foncée (le bon son est joue et le choix est garde
# tant qu'elle reste a l'image).

# Police pour les etiquettes (Pillow : gere les accents, pas cv2.putText)
LABEL_FONT = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)

_mci = ctypes.windll.winmm.mciSendStringW


def load_sounds():
    for group, path in SOUNDS.items():
        if not path.exists():
            print(f"Son introuvable : {path}")
            continue
        _mci(f'open "{path}" type mpegvideo alias son{group}', None, 0, None)


def play_sound(group):
    """Coupe le son en cours et joue celui du groupe."""
    for g in SOUNDS:
        _mci(f"stop son{g}", None, 0, None)
    _mci(f"play son{group} from 0", None, 0, None)


def close_sounds():
    for group in SOUNDS:
        _mci(f"close son{group}", None, 0, None)


# --- Mesure de la peau -----------------------------------------------------
def white_balance(frame):
    """Balance des blancs 'gray world' : enleve la teinte de l'eclairage."""
    img = frame.astype(np.float32)
    means = img.reshape(-1, 3).mean(axis=0)
    img *= means.mean() / np.maximum(means, 1)
    return np.clip(img, 0, 255).astype(np.uint8)


_clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8))


def enhance_display(frame):
    """Image plus belle pour l'AFFICHAGE seulement (la mesure de la peau
    utilise l'image originale) : contraste local + nettete."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = _clahe.apply(lab[:, :, 0])          # contraste local
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    blur = cv2.GaussianBlur(img, (0, 0), 1.2)
    return cv2.addWeighted(img, 1.6, blur, -0.6, 0)     # nettete


def is_frontal(pts):
    """Visage face a la camera ? (tete baissee/tournee = visage dans
    l'ombre -> la couleur mesuree serait fausse)
    pitch : nez entre front (10) et menton (152) ; ~0.62 de face, >0.70 baissee
    yaw   : nez par rapport au milieu des joues (234, 454) ; ~0 de face"""
    pitch = (pts[1, 1] - pts[10, 1]) / max(pts[152, 1] - pts[10, 1], 1)
    yaw = (pts[1, 0] - (pts[234, 0] + pts[454, 0]) / 2) / \
        max(abs(pts[454, 0] - pts[234, 0]), 1)
    return pitch < MAX_PITCH and abs(yaw) < MAX_YAW


def get_faces(mesh_results, width, height):
    """Liste de visages : boite + points de mesure de la peau."""
    faces = []
    if not mesh_results.multi_face_landmarks:
        return faces
    for landmarks in mesh_results.multi_face_landmarks:
        pts = np.array([(lm.x * width, lm.y * height)
                        for lm in landmarks.landmark])
        x1, y1 = np.clip(pts.min(axis=0), 0, [width - 1, height - 1])
        x2, y2 = np.clip(pts.max(axis=0), 0, [width - 1, height - 1])
        if x2 - x1 < 10 or y2 - y1 < 10:
            continue
        skin_pts = [tuple(pts[i].astype(int)) for i in SKIN_LANDMARKS]
        faces.append({
            "box": (int(x1), int(y1), int(x2), int(y2)),
            "center": ((x1 + x2) / 2, (y1 + y2) / 2),
            "skin_pts": skin_pts,
            "frontal": is_frontal(pts),
        })
    return faces


def linear_luminance(pixels):
    """Luminance physique (lineaire, 0..1) de pixels BGR."""
    c = pixels.reshape(-1, 3).astype(np.float32) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.0722 * c[:, 0] + 0.7152 * c[:, 1] + 0.2126 * c[:, 2]


def scene_reference(frame, person_mask):
    """Luminance des surfaces claires de l'arriere-plan (mur...).
    Les pixels 'brules' (fenetre, lampe) sont exclus."""
    frame, person_mask = frame[::4, ::4], person_mask[::4, ::4]  # + rapide
    background = frame[(person_mask == 0) & (frame.max(axis=2) < 245)]
    if len(background) < 100:
        background = frame[frame.max(axis=2) < 245]
    if len(background) < 100:
        return None
    return float(np.percentile(linear_luminance(background), 80))


def add_detected_faces(faces, det_results, width, height):
    """Ajoute les visages de Face Detection que Face Mesh n'a pas trouves.
    Peau mesuree sur les joues et le front (positions dans la boite)."""
    if not det_results.detections:
        return faces
    for det in det_results.detections:
        b = det.location_data.relative_bounding_box
        x1, y1 = int(b.xmin * width), int(b.ymin * height)
        w, h = int(b.width * width), int(b.height * height)
        cx, cy = x1 + w / 2, y1 + h / 2
        if w < 12 or h < 12:
            continue
        if any(f["box"][0] <= cx <= f["box"][2] and f["box"][1] <= cy <= f["box"][3]
               for f in faces):
            continue   # deja trouve par Face Mesh
        pts = [(x1 + 0.28 * w, y1 + 0.62 * h), (x1 + 0.72 * w, y1 + 0.62 * h),
               (x1 + 0.30 * w, y1 + 0.50 * h), (x1 + 0.70 * w, y1 + 0.50 * h)]  # joues
        skin_pts = [(int(np.clip(px, 0, width - 1)), int(np.clip(py, 0, height - 1)))
                    for px, py in pts]
        faces.append({
            "box": (max(x1, 0), max(y1, 0), min(x1 + w, width - 1),
                    min(y1 + h, height - 1)),
            "center": (cx, cy),
            "skin_pts": skin_pts,
        })
    return faces


def measure_tone(frame, face, ref):
    """Teint pris en petits disques sur le front et les joues."""
    x1, _, x2, _ = face["box"]
    radius = max(int((x2 - x1) * 0.05), 3)
    sample = np.zeros(frame.shape[:2], dtype=np.uint8)
    for p in face["skin_pts"]:
        cv2.circle(sample, p, radius, 255, -1)
    return tone_from_pixels(frame[sample > 0], ref)


def tone_from_pixels(pixels, ref):
    """Rapport luminance peau / luminance du mur (0..1).
    Independant du reglage d'exposition de la camera."""
    if ref is None or ref <= 0 or len(pixels) < 30:
        return None
    pixels = pixels.reshape(-1, 3)
    pixels = pixels[pixels.max(axis=1) < 250]   # pas les pixels eblouis
    if len(pixels) < 30:
        return None
    Y = linear_luminance(pixels)
    # Enlever reflets (trop clairs) et ombres (trop sombres)
    low, high = np.percentile(Y, [15, 85])
    keep = (Y >= low) & (Y <= high)
    if keep.sum() < 15:
        return None

    # 1) Luminosite de la peau corrigee par le mur (annule l'exposition)
    y_skin = float(np.median(Y[keep])) / ref * WALL_REFLECTANCE
    y_skin = min(max(y_skin, 1e-4), 1.0)
    L = 116 * y_skin ** (1 / 3) - 16 if y_skin > 0.008856 else 903.3 * y_skin
    # 2) Teinte jaune/brune b* de la peau (CIELAB)
    lab = cv2.cvtColor(pixels[keep].reshape(-1, 1, 3).astype(np.float32) / 255,
                       cv2.COLOR_BGR2Lab).reshape(-1, 3)
    # Webcam = couleurs ternes : b* sous-estime -> on le borne a une valeur
    # realiste pour la peau (sinon l'ITA part aux extremes)
    b = float(np.clip(np.median(lab[:, 2]), SKIN_B_MIN, 30.0))
    # 3) ITA (Individual Typology Angle) en degres
    return float(np.degrees(np.arctan2(L - 50.0, b)))


def fitzpatrick_type(ita):
    """Type de peau I a VI selon l'ITA (seuils standards)."""
    for limit, skin_type in FITZPATRICK:
        if ita > limit:
            return skin_type
    return 6


def skin_mask_for(ycrcb, individual_mask, face):
    """Pixels de peau de CETTE personne (couleur apprise sur son visage)."""
    if face is not None:
        x1, _, x2, _ = face["box"]
        radius = max(int((x2 - x1) * 0.05), 3)
        sample = np.zeros(ycrcb.shape[:2], dtype=np.uint8)
        for p in face["skin_pts"]:
            cv2.circle(sample, p, radius, 255, -1)
        if cv2.countNonZero(sample) < 30:
            face = None          # visage trop petit : plage generique
    if face is None:
        low = np.array([0, 135, 85], np.uint8)
        high = np.array([255, 180, 135], np.uint8)
    else:
        sample = np.zeros(ycrcb.shape[:2], dtype=np.uint8)
        x1, _, x2, _ = face["box"]
        radius = max(int((x2 - x1) * 0.05), 3)
        for p in face["skin_pts"]:
            cv2.circle(sample, p, radius, 255, -1)
        pixels = ycrcb[sample > 0].astype(np.float32)
        mean = pixels.mean(axis=0)
        std = np.maximum(pixels.std(axis=0), [0, 4, 4])
        # Couleur proche de celle du visage (2 ecarts-types)
        low = np.array([20, mean[1] - 2 * std[1], mean[2] - 2 * std[2]])
        high = np.array([255, mean[1] + 2 * std[1], mean[2] + 2 * std[2]])
        low, high = np.clip(low, 0, 255).astype(np.uint8), \
            np.clip(high, 0, 255).astype(np.uint8)
    skin = cv2.inRange(ycrcb, low, high)
    # ET une vraie couleur de peau : les couleurs neutres (noir, blanc, gris :
    # Cr ~ 128) des vetements sont exclues
    skin = cv2.bitwise_and(skin, cv2.inRange(
        ycrcb, np.array([25, 136, 77], np.uint8),
        np.array([250, 175, 127], np.uint8)))
    skin = cv2.bitwise_and(skin, individual_mask)
    skin = cv2.morphologyEx(skin, cv2.MORPH_OPEN, KERNEL)
    return cv2.morphologyEx(skin, cv2.MORPH_CLOSE, KERNEL)


# --- Personnes -------------------------------------------------------------
def split_individuals(person_mask, faces):
    """Un masque par personne. Retourne une liste de (masque, visage|None)."""
    individuals = []
    count, labels, stats, _ = cv2.connectedComponentsWithStats(person_mask, 8)
    for label in range(1, count):
        if stats[label, cv2.CC_STAT_AREA] < MIN_PERSON_AREA:
            continue
        component = np.where(labels == label, 255, 0).astype(np.uint8)
        inside = [f for f in faces
                  if component[int(f["center"][1]), int(f["center"][0])] > 0]
        if len(inside) <= 1:
            individuals.append((component, inside[0] if inside else None))
            continue
        # Personnes collees : chaque colonne va au visage le plus proche
        centers_x = np.array([f["center"][0] for f in inside])
        cols = np.arange(person_mask.shape[1])
        nearest = np.argmin(np.abs(cols[:, None] - centers_x[None, :]), axis=1)
        for i, face in enumerate(inside):
            column_mask = np.zeros_like(component)
            column_mask[:, nearest == i] = 255
            part = cv2.bitwise_and(component, column_mask)
            if cv2.countNonZero(part) >= MIN_PERSON_AREA // 2:
                individuals.append((part, face))
    # Visages hors masque (masque rate) : on garde quand meme la personne
    used = {id(f) for _, f in individuals if f is not None}
    for f in faces:
        if id(f) not in used:
            m = np.zeros_like(person_mask)
            x1, y1, x2, y2 = f["box"]
            m[y1:y2, x1:x2] = 255
            individuals.append((m, f))
    return individuals


class Tracker:
    """Suit chaque personne d'une image a l'autre et decide son teint."""

    def __init__(self):
        self.tracks = []
        self.next_id = 1

    def update(self, people, width):
        """people : liste de dict avec 'center' et 'ita' (ou None)."""
        for t in self.tracks:
            t["missing"] += 1
        free = list(self.tracks)
        for person in people:
            best, best_d = None, width * 0.25
            for t in free:
                d = np.hypot(person["center"][0] - t["center"][0],
                             person["center"][1] - t["center"][1])
                if d < best_d:
                    best, best_d = t, d
            if best is None:
                best = {"id": self.next_id, "ita": deque(maxlen=ITA_HISTORY),
                        "seen": 0, "group": None, "played": None}
                self.next_id += 1
                self.tracks.append(best)
            else:
                free.remove(best)
            best.update(center=person["center"], missing=0)
            best["seen"] += 1
            if person["ita"] is not None:
                best["ita"].append(person["ita"])
            self._decide(best)
            person["track"] = best
        self.tracks = [t for t in self.tracks if t["missing"] <= LOST_FRAMES]
        self._compare()

    def _compare(self):
        """Compare les personnes visibles entre elles (meme eclairage)."""
        if not USE_COMPARISON:
            return
        ready = [t for t in self.tracks
                 if t["missing"] == 0 and "ita_med" in t
                 and not t.get("manual")]   # un choix au clic n'est pas touche
        if len(ready) < 2:
            return
        ready.sort(key=lambda t: t["ita_med"])
        # Le plus grand ecart d'ITA (degres) entre deux personnes voisines
        gaps = [ready[i + 1]["ita_med"] - ready[i]["ita_med"]
                for i in range(len(ready) - 1)]
        i = int(np.argmax(gaps))
        if gaps[i] < RELATIVE_GAP:
            return
        for k, t in enumerate(ready):
            t["group"] = 2 if k <= i else 1
            t["locked"] = True

    @staticmethod
    def _decide(t):
        if t["seen"] < CONFIRM_FRAMES or len(t["ita"]) < 3:
            return
        med = float(np.median(t["ita"]))
        t["ita_med"] = med
        if t.get("locked"):      # deja classe par comparaison : on garde
            return
        # Limite entre type III et type IV = ITA 28 degres
        limit = FITZPATRICK[2][0]
        if t["group"] is None:
            t["group"] = 1 if med > limit else 2
        elif t["group"] == 1 and med < limit - HYSTERESIS:
            t["group"] = 2
        elif t["group"] == 2 and med > limit + HYSTERESIS:
            t["group"] = 1


def open_camera(tries=5):
    """Ouvre la camera ; reessaie si elle est occupee (autre programme)."""
    for attempt in range(tries):
        for api in (cv2.CAP_MSMF, cv2.CAP_DSHOW):
            cap = cv2.VideoCapture(0, api)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # haute resolution
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            if cap.isOpened() and cap.read()[0]:
                return cap
            cap.release()
        print(f"Camera occupee, nouvel essai ({attempt + 1}/{tries})...")
        time.sleep(1)
    return None


def main():
    cap = open_camera()
    if cap is None:
        print("Camera introuvable ou occupee.\n"
              "-> Ferme l'app Camera, Teams, Zoom, ou une autre fenetre de "
              "l'exercice 7 (gestionnaire des taches : python.exe / "
              "pythonw.exe), puis relance.")
        return

    load_sounds()
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_TOPMOST, 1)
    tracker = Tracker()
    flash_until = 0.0
    frame_idx = 0
    shown = []   # (masque, track) des personnes affichees, pour le clic

    def on_click(event, mx, my, flags, param):
        """Clic sur une personne : inverse Blanc <-> Noir."""
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for mask, track in shown:
            if 0 <= my < mask.shape[0] and 0 <= mx < mask.shape[1] \
                    and mask[my, mx] > 0:
                current = track["group"] or 1
                track["group"] = 2 if current == 1 else 1
                track["locked"] = track["manual"] = True
                return

    cv2.setMouseCallback(WINDOW, on_click)

    try:
        while True:
            success, frame = cap.read()
            if not success:
                break
            frame = cv2.flip(frame, 1)
            frame_idx += 1
            height, width = frame.shape[:2]

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            seg = segmenter.process(rgb)
            faces = get_faces(face_mesh.process(rgb), width, height)
            faces = add_detected_faces(faces, face_detector.process(rgb),
                                       width, height)
            faces = add_detected_faces(faces, face_detector_near.process(rgb),
                                       width, height)

            person_mask = (seg.segmentation_mask > 0.6).astype(np.uint8) * 255
            person_mask = cv2.morphologyEx(person_mask, cv2.MORPH_OPEN, KERNEL)
            ref = scene_reference(frame, person_mask)
            ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
            individuals = split_individuals(person_mask, faces)

            # Teint de chaque personne : visage si visible, sinon sa peau
            people = []
            for ind_mask, face in individuals:
                x, y, w, h = cv2.boundingRect(ind_mask)
                skin = skin_mask_for(ycrcb, ind_mask, face)
                if face is not None:
                    # Visage + peau du corps (bras, mains, cou). La peau du
                    # corps est trouvee avec la couleur apprise sur le visage,
                    # donc les vetements ne sont pas pris.
                    ita_face = measure_tone(frame, face, ref)
                    body = skin.copy()
                    fx1, fy1, fx2, fy2 = face["box"]
                    body[fy1:fy2, fx1:fx2] = 0        # le visage compte deja
                    pix = frame[body > 0]
                    ita_body = tone_from_pixels(pix, ref) \
                        if len(pix) > 400 else None
                    values = [v for v in (ita_face, ita_body) if v is not None]
                    ita = float(np.mean(values)) if values else None
                    source = "visage + corps" if ita_body is not None else "visage"
                else:
                    # Haut de la personne seulement (tete / cou) :
                    # jamais les vetements
                    head = np.zeros_like(skin)
                    head[y:y + max(int(min(h * 0.3, w * 0.8)), 1), x:x + w] = 255
                    pix = frame[cv2.bitwise_and(skin, head) > 0]
                    ita = tone_from_pixels(pix, ref) if len(pix) > 300 else None
                    source = "peau"
                if frame_idx <= WARMUP_FRAMES:   # camera pas encore stable
                    ita = None
                if face is not None and not face.get("frontal", True):
                    ita = None   # tete baissee / tournee : visage dans l'ombre
                people.append({
                    "mask": ind_mask, "face": face, "skin": skin,
                    "center": (x + w / 2, y + min(h, w) / 2),
                    "ita": ita, "source": source,
                })
            tracker.update(people, width)

            # Son : nouvelle personne OU teint qui change -> on joue tout de suite
            for t in tracker.tracks:
                if t["missing"] == 0 and t["group"] is not None \
                        and t["group"] != t["played"]:
                    play_sound(t["group"])
                    t["played"] = t["group"]
                    flash_until = time.time() + 0.5

            output = frame.copy()   # couleurs originales de la camera
            shown = [(p["mask"], p["track"]) for p in people]
            labels = []
            for num, person in enumerate(
                    sorted(people, key=lambda p: p["center"][0]), start=1):
                ind_mask, face, skin = person["mask"], person["face"], person["skin"]
                track = person["track"]
                color = PERSON_COLORS[track["id"] % len(PERSON_COLORS)]

                # Contour de la personne seulement (rien sur le visage)
                contours, _ = cv2.findContours(
                    ind_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(output, contours, -1, color, 3)

                # Etiquette
                x, y, _, _ = cv2.boundingRect(ind_mask)
                if track["group"] is None:
                    label = f"P{num} : analyse..."
                else:
                    label = f"P{num} : {GROUP_NAMES[track['group']]}"
                labels.append((label, x, y, color))

            # Etiquettes dessinees avec Pillow (accents OK)
            if labels:
                pil = Image.fromarray(cv2.cvtColor(output, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(pil)
                for label, x, y, color in labels:
                    l, t, r, b = draw.textbbox((0, 0), label, font=LABEL_FONT)
                    tw, th = r - l, b - t
                    ty = max(y - th - 14, 0)
                    draw.rectangle((x, ty, x + tw + 14, ty + th + 14),
                                   fill=color[::-1])          # BGR -> RGB
                    draw.text((x + 7 - l, ty + 7 - t), label,
                              font=LABEL_FONT, fill=(255, 255, 255))
                output = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

            if time.time() < flash_until:   # cadre jaune quand un son part
                cv2.rectangle(output, (0, 0), (width - 1, height - 1),
                              (0, 255, 255), 8)

            cv2.imshow(WINDOW, output)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        segmenter.close()
        face_mesh.close()
        face_detector.close()
        face_detector_near.close()
        close_sounds()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
