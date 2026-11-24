import cv2
from quickHand import HandDetector

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
            hands, image = detector.findHands(image, draw=True)#,flipType=False)
            for hand in hands:
                detector.infoOnHand(image, hand)
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
