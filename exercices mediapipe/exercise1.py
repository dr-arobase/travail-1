import cv2
from quickHand import HandDetector

# Pour la capture video:
# Vous pouvez passez en paramètre une valeur de -1 à 0 pour utiliser une webcam.
# Vous pouvez donner l'emplacement d'une vidéo. Exemple: "./videoAmusante.mp4" .
cap = cv2.VideoCapture(0)
detector = HandDetector(detectionCon=0.8,maxHands=2)

def main():
    cv2.namedWindow("Image", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Image", 960, 720)
    try:
        while True:
            success, image = cap.read()
            if not success:
                break
            detector.findHands(image, draw=True)#,flipType=False)
            cv2.imshow("Image", image)
            if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                break
            if cv2.getWindowProperty("Image", cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
