import time
from picamera2 import Picamera2, Preview

# Boucle du menu principal
while True:
    print("\n" + "="*40)
    print("     MENU CAMERA RASPBERRY PI")
    print("="*40)
    print("1. Me voir en direct (Aperçu vidéo)")
    print("2. Prendre une photo")
    print("3. Enregistrer une vidéo (5 secondes)")
    print("4. Quitter")
    print("="*40)
    
    choix = input("Faites votre choix (1, 2, 3 ou 4) : ")
    
    if choix == '1':
        print("\n-> Ouverture de l'aperçu en direct.")
        print("   (Une fenêtre vidéo va s'ouvrir. Appuyez sur 'Entrée' dans ce terminal pour fermer l'aperçu)")
        
        # Initialisation propre pour l'aperçu
        picam2 = Picamera2()
        picam2.start_preview(Preview.QTGL)
        picam2.start()
        
        # Le programme reste ici en vie jusqu'à ce que vous appuyiez sur Entrée
        input()
        
        # Fermeture propre de la caméra
        picam2.stop()
        print("-> Aperçu fermé.")
        
    elif choix == '2':
        print("\n-> Prise de la photo en cours...")
        picam2 = Picamera2()
        picam2.start()
        time.sleep(2)  # Pause pour laisser la caméra ajuster la lumière
        picam2.capture_file("photo.jpg")
        picam2.stop()
        print("-> Succès ! Photo enregistrée sous 'photo.jpg'")
        
    elif choix == '3':
        print("\n-> Enregistrement de la vidéo (5 secondes)...")
        picam2 = Picamera2()
        config = picam2.create_video_configuration(main={"size": (1280, 720)})
        picam2.configure(config)
        picam2.start()
        time.sleep(1)
        picam2.start_and_record_video("video.mp4", duration=5)
        picam2.stop()
        print("-> Succès ! Vidéo enregistrée sous 'video.mp4'")
        
    elif choix == '4':
        print("\nFermeture du programme. Au revoir !")
        break
    else:
        print("\n[!] Choix invalide, veuillez entrer 1, 2, 3 ou 4.")