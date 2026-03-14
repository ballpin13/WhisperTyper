# WhisperTyper 🎙️
**F9 röstinmatning med Whisper – lokalt, på svenska**

---

## Installation

1. Se till att **Python 3.9+** är installerat (python.org)
2. Kör `installera.bat` (högerklicka → Kör som administratör)
3. Installera **ffmpeg** om det saknas:
   ```
   winget install ffmpeg
   ```
   (eller ladda ned från ffmpeg.org och lägg i PATH)

---

## Användning

1. Kör `starta.bat` (eller `python whisper_typer.py`)
2. Klicka i valfri textruta (e-post, Word, webbläsare, anteckningar...)
3. **Håll ned F9** och tala
4. **Släpp** kortkommandot → Whisper transkriberar → texten klistras in

---

## Modeller

Ändra `WHISPER_MODEL` i `whisper_typer.py`:

| Modell   | Storlek | Hastighet | Kvalitet svenska |
|----------|---------|-----------|-----------------|
| `tiny`   | ~75 MB  | Mycket snabb | OK            |
| `base`   | ~150 MB | Snabb       | Bra            |
| `small`  | ~500 MB | Medel       | **Rekommenderas** |
| `medium` | ~1.5 GB | Långsam     | Utmärkt        |
| `large`  | ~3 GB   | Mycket långsam | Bäst        |

---

## Autostart vid inloggning

1. Tryck **Win+R**, skriv `shell:startup`, tryck Enter
2. Kopiera en genväg till `starta.bat` i den mappen

---

## Felsökning

**"Ingen ljud inspelat"** – Kontrollera att rätt mikrofon är vald i Windows Ljud-inställningar.

**Fel på PyAudio** – Prova:
```
pip install pipwin
pipwin install pyaudio
```

**Texten skrivs inte in** – Scriptet behöver köras med administratörsbehörighet för att `keyboard`-biblioteket ska fungera i alla appar. Högerklicka på `starta.bat` → Kör som administratör.

**Långsam första körning** – Whisper-modellen laddas in i RAM vid start (~2-5 sek), sedan går det snabbt.

---

## Konfiguration

Alla inställningar nås via **Inställningar-fliken** i appen och sparas i `config.json`.

- **Whisper-modell** — tiny/base/small/medium/large
- **Språk** — Svenska, Engelska, Auto-detect
- **Enhet** — Auto, CPU, GPU (NVIDIA CUDA)
- **Kortkommandon** — Diktering (F9), AI-redigering (Ctrl+F9)
- **Ordlista** — Ange namn och termer (ett per rad) som Whisper ska känna igen korrekt
- **AI-redigering** — Ollama (lokal) eller Cloud (OpenAI/Anthropic)
- **Promptprofiler** — Anpassa AI-instruktioner
- **Ljud & notiser** — Ljudeffekter och popup-notiser
