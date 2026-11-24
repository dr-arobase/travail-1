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
            if len(hands) == 1:
                hand = hands[0]
                detector.infoOnHand(image, hand, [detector.fingersUp(hand)])
            elif len(hands) == 2:
                length, info, img = detector.findDistance(
                    hands[0]["lmList"][8][1:],
                    hands[1]["lmList"][8][1:],
                    image,
                )
                distance = f"distance: {length:.1f}"
                detector.infoOnHand(image, hands[0],
                                    [f"{detector.fingersUp(hands[0])} doigts", distance])
                detector.infoOnHand(image, hands[1],
                                    [f"{detector.fingersUp(hands[1])} doigts", distance])
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
