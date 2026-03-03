@echo off
echo ================================================
echo   Installation - MCP Organismes de Formation
echo ================================================
echo.

REM Vérifier Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERREUR : Python n'est pas installe.
    echo Telechargez-le ici : https://www.python.org/downloads/
    echo IMPORTANT : Cochez "Add Python to PATH" lors de l'installation.
    pause
    exit /b 1
)

echo [1/2] Installation des dependances...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERREUR : L'installation des dependances a echoue.
    pause
    exit /b 1
)

echo.
echo [2/2] Creation du dossier de donnees...
if not exist "data" mkdir data

echo.
echo ================================================
echo   Installation terminee !
echo ================================================
echo.
echo Pour utiliser ce serveur MCP avec Claude :
echo.
echo 1. Ouvrez VS Code
echo 2. Ouvrez les parametres Claude (Ctrl+Shift+P puis "Claude: Open Settings")
echo 3. Ajoutez ce serveur MCP dans la configuration
echo    (voir le fichier LISEZMOI.md pour les details)
echo.
pause
