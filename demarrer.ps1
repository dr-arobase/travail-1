# Démarre la porte magique (itération 3) : active l'environnement Python
# puis lance le contrôle par gestes. Utilisation, depuis ce dossier :
#     .\demarrer.ps1
# Si PowerShell bloque les scripts :
#     Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# 1. Activer l'environnement Python (MediaPipe, OpenCV, pyserial, aliot)
& "$PSScriptRoot\venv_mediapipe\Scripts\Activate.ps1"
$env:PYTHONIOENCODING = "utf-8"

# 2. Objets ALIOT à connecter (projet « Porte magique » et rasp_door)
if (-not $env:PORTE_OBJETS) { $env:PORTE_OBJETS = "porte_magique,rasp_door" }

# 3. Lancer la porte
Write-Host "Environnement actif : $(python --version)" -ForegroundColor Magenta
Write-Host "Demarrage de la porte magique... (q ou Echap pour quitter)" -ForegroundColor Magenta
python "porte magique\iteration3_gestes.py"
