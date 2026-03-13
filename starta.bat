@echo off
:: Starta WhisperTyper minimerat i bakgrunden
:: Lägg en genväg till denna fil i:
::   shell:startup  (Win+R -> shell:startup)
:: ...så startar den automatiskt vid inloggning.

start "WhisperTyper" /min python "%~dp0whisper_typer.py"
