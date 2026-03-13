@echo off
echo =============================================
echo  WhisperTyper - Installation
echo =============================================
echo.

:: Kontrollera Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEL] Python hittades inte. Installera Python 3.9+ fran python.org
    pause
    exit /b 1
)

echo [1/4] Uppgraderar pip...
python -m pip install --upgrade pip --quiet

echo [2/4] Installerar PyAudio...
pip install pyaudio --quiet
if errorlevel 1 (
    echo [!] PyAudio misslyckades. Provar med pipwin...
    pip install pipwin --quiet
    pipwin install pyaudio --quiet
)

echo [3/4] Installerar Whisper och beroenden...
pip install openai-whisper --quiet
pip install keyboard pyperclip --quiet

echo [4/4] Installerar ffmpeg (kravs av Whisper)...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [!] ffmpeg hittades inte.
    echo     Installera via: winget install ffmpeg
    echo     Eller ladda ned fran https://ffmpeg.org/download.html
    echo     och lagg till i PATH.
) else (
    echo [OK] ffmpeg finns redan.
)

echo.
echo =============================================
echo  Installation klar!
echo  Kör whisper_typer.py för att starta.
echo  Första gången laddas Whisper-modellen ned (~500MB för 'small').
echo =============================================
pause
