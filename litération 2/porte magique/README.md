# Porte magique - itération 2

Cette version reprend le sketch de la porte du travail 1 et ajoute la
communication avec ALIOT, sur le même modèle que l'exemple de la serre.

## Arduino

Téléverser [porte_magique.ino](./porte_magique.ino). Le sketch utilise les
mêmes broches que le travail 1 et communique à 9600 bauds.

## Python

Installer `pyserial` et `aliot`, puis lancer `iteration2.py`. Le port Arduino est
détecté automatiquement. Pour imposer un port :

```powershell
$env:PORTE_MAGIQUE_PORT = "COM6"
python iteration2.py
```

Avant le lancement, remplacer les deux valeurs `REMPLACER_...` dans
[config.ini](./config.ini) par l'identifiant et le jeton de l'objet ALIOT.

Les données publiées sont `actif`, `etat`, `presence`, `distance`, `angle` et
`evenement`. Les actions ALIOT sont `ouvrir_porte`, `fermer_porte`,
`activer_systeme` et `desactiver_systeme`.
