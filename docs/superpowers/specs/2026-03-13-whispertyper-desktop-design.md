# WhisperTyper Desktop — Designspecifikation

## Översikt

WhisperTyper Desktop är en fristående Windows-app för röstdiktering med lokal Whisper-transkribering och AI-redigering. Appen lever i system tray och erbjuder ett dashboard med live-status, historik och inställningar.

**Arbetsnamn:** WhisperTyper (kan bytas — namnet styrs av en enda konstant)

## Teknikstack

- **PySide6** — GUI-ramverk (cross-platform-redo, LGPL-licens)
- **OpenAI Whisper** — Lokal tal-till-text
- **Ollama** — Lokal AI-redigering (standard)
- **OpenAI / Anthropic API** — Valfri cloud AI-redigering
- **PyInstaller** — Paketering till fristående `.exe`
- **pynput** — Cross-platform hotkey-lyssning (ersätter `keyboard`)
- **PyAudio** — Mikrofoninspelning
- **pyperclip** — Clipboard-hantering

## Visuell stil

Ljus och ren design — vit bakgrund, subtila ramar, tydliga kontraster. Google/macOS-känsla. Typsnitt: systemtypsnitt (Segoe UI på Windows).

## Arkitektur

### Filstruktur

```
WhisperTyper/
  main.py                # Startpunkt — tray + fönster
  engine.py              # Inspelning, Whisper, AI-logik (bakgrundsmotor)
  config.py              # Sparar/laddar inställningar (JSON)
  ui/
    dashboard.py         # Huvudfönster med flikar
    tab_live.py          # Live-flik
    tab_history.py       # Historik-flik
    tab_settings.py      # Inställningar-flik
  assets/
    icon_ready.png       # Tray-ikon — redo (grön)
    icon_recording.png   # Tray-ikon — spelar in (röd)
    icon_transcribing.png # Tray-ikon — transkriberar (gul)
    icon_ai.png          # Tray-ikon — AI bearbetar (blå)
    sound_start.wav      # Ljudeffekt — inspelning startar
    sound_done.wav       # Ljudeffekt — transkribering klar
  installer/
    build_installer.py   # PyInstaller build-script
```

### Komponentdiagram

```
┌─────────────────────────────────────────────┐
│                   main.py                    │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │ System Tray  │  │  Dashboard (flikar)  │  │
│  │  - Ikon      │  │  ┌──────┐           │  │
│  │  - Meny      │  │  │ Live │ Historik   │  │
│  │  - Notiser   │  │  │      │ Inställn.  │  │
│  └──────┬───────┘  └──────┬──────────────┘  │
│         │                 │                  │
│         └────────┬────────┘                  │
│                  ▼                           │
│  ┌──────────────────────────────────────┐    │
│  │           engine.py                   │    │
│  │  - Inspelning (PyAudio)              │    │
│  │  - Transkribering (Whisper)          │    │
│  │  - AI-redigering (Ollama / Cloud)    │    │
│  │  - Hotkey-lyssning (pynput)          │    │
│  │  - Ljudeffekter                      │    │
│  └──────────────────────────────────────┘    │
│                  ▼                           │
│  ┌──────────────────────────────────────┐    │
│  │           config.py                   │    │
│  │  - config.json (inställningar)       │    │
│  │  - history.json (historik)           │    │
│  │  - prompts.json (promptprofiler)     │    │
│  └──────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

### Hotkey-interaktionsmodell

**Hold-to-record:** Användaren håller ned tangenten (F9/F10) för att spela in och släpper för att stoppa — samma modell som nuvarande prototyp. Detta är inte konfigurerbart; modellen är alltid hold-to-record.

### Trådningsmodell

Engine.py kör alla tunga operationer (inspelning, Whisper-transkribering, Ollama/Cloud API-anrop) i bakgrundstrådar via `QThread`. GUI:t uppdateras enbart via Qt-signaler, som är trådsäkra i Qt. Huvudtråden (Qt event loop) blockeras aldrig.

### Text-injektion

Transkriberad text skrivs in i det aktiva fönstret via clipboard: texten kopieras till clipboard, sedan simuleras `Ctrl+V` med `pynput.keyboard.Controller`. Efter inklistring återställs clipboard till sitt tidigare innehåll. Vid AI-redigering (F10) raderas den senaste texten först genom att simulera N backspace-knapptryckningar, sedan klistras den nya texten in. Om det aktiva fönstret har bytts sedan senaste textinjektionen hoppas backspace-raderingen över och den AI-redigerade texten klistras in som ny text istället.

### Modelladdning och startup

Vid uppstart visar tray-ikonen en **grå** ikon ("Laddar modell..."). Whisper-modellen laddas i en bakgrundstråd. Under laddning ignoreras knapptryckningar på F9/F10 (ingen inspelning startar). När modellen är redo byter ikonen till grön och användaren meddelas via en popup-notis ("WhisperTyper redo!").

### Kommunikation mellan komponenter

Engine.py exponerar Qt-signaler som GUI:t lyssnar på:

- `model_loading` — Tray visar grå ikon, Live-flik visar "Laddar modell..."
- `model_ready` — Tray byter till grön ikon, notis visas
- `recording_started` — Tray byter ikon, Live-flik visar "Spelar in..."
- `recording_stopped(duration)` — Tray byter ikon
- `transcription_started` — Tray byter ikon, Live-flik visar "Transkriberar..."
- `transcription_done(text)` — Live-flik visar text, historik uppdateras, notis visas
- `ai_started` — Tray byter ikon
- `ai_done(original, edited)` — Live-flik visar redigerad text, historik uppdateras

## System Tray

### Ikon

Färgskiftande ikon som visar status:
- **Grå** — Laddar modell (startup)
- **Grön** — Redo att diktera
- **Röd** — Spelar in (pulserande om möjligt)
- **Gul** — Transkriberar med Whisper
- **Blå** — AI bearbetar

### Högerklicksmeny

1. Senaste transkriberingen, trunkerad till 80 tecken (klicka för att kopiera till clipboard)
2. Separator
3. Aktiv promptprofil → undermeny med alla profiler
4. Separator
5. Öppna dashboard
6. Inställningar (öppnar dashboard på inställningsfliken)
7. Separator
8. Avsluta

### Vänsterklick

Togglar dashboard-fönstret (visa/göm).

### Popup-notiser

- Visas vid avslutad transkribering med den transkriberade texten
- Valfri — kan stängas av i inställningar
- Varaktighet konfigurerbar (2-10 sek, standard 4 sek)
- Klick på notisen öppnar dashboard (best-effort — `messageClicked` är inte 100% pålitlig på alla Windows-versioner)

## Dashboard — Live-flik

### Innehåll

- **Statusindikator** — Färgad cirkel + statustext ("Redo", "Spelar in...", "Transkriberar...", "AI bearbetar...")
- **Senaste transkribering** — Texten, tidsstämpel, inspelningsvaraktighet
- **Snabbknappar:**
  - Kopiera — kopierar senaste texten till clipboard
  - Redigera med AI — öppnar textfält för att skriva en redigeringsinstruktion (alternativ till F10-röst)
- **Aktiv promptprofil** — Dropdown för snabbt byte

### Beteende

- Uppdateras i realtid via signaler från engine
- AI-redigeringsknappen visar ett textfält + skicka-knapp. Resultatet ersätter senaste texten.

## Dashboard — Historik-flik

### Innehåll

- **Sökfält** — Filtrerar historiken i realtid
- **Lista** — Varje rad visar:
  - Transkriberad text (trunkerad om lång)
  - Tidsstämpel
  - Varaktighet
  - Ikon om texten redigerats med AI
- **Högerklicksmeny på rad** — Kopiera, Redigera med AI (öppnar modal med textfält för instruktion, resultat skapar ny historikpost), Ta bort
- **Rensa historik-knapp** — Med bekräftelsedialog ("Är du säker? Detta går inte att ångra.")

### Lagring

- Sparas i `history.json`
- Max antal konfigurerbart (100/500/1000/obegränsad, standard 500)

## Dashboard — Inställningar-flik

Organiserat i visuella sektioner med rubriker.

### Whisper

| Inställning | Typ | Standard | Beskrivning |
|---|---|---|---|
| Modell | Dropdown | medium | tiny/base/small/medium/large |
| Språk | Dropdown | Svenska | Svenska, Engelska, Auto-detect |
| Enhet | Info-text | (auto) | Visar GPU/CPU — ej redigerbar |

### Kortkommandon

| Inställning | Typ | Standard |
|---|---|---|
| Diktera | Tangentfångare | F9 |
| AI-redigering | Tangentfångare | F10 |

Tangentfångare: klicka på fältet, tryck önskad tangent. Validering: samma tangent kan inte tilldelas båda kortkommandona — inline-felmeddelande visas vid konflikt.

### AI-redigering

| Inställning | Typ | Standard | Villkor |
|---|---|---|---|
| Provider | Dropdown | Lokal (Ollama) | — |
| Ollama-modell | Dropdown | mistral:7b | Visas om Ollama valt |
| Cloud-provider | Dropdown | OpenAI | Visas om cloud valt (OpenAI / Anthropic) |
| Cloud-modell | Dropdown | gpt-4o-mini | Visas om cloud valt, modeller filtreras per provider |
| API-nyckel | Lösenordsfält | — | Visas om cloud valt |

Ollama-dropdown hämtar installerade modeller automatiskt via API. Om Ollama inte körs visas placeholder-text ("Ollama ej tillgänglig — starta Ollama") och dropdown är inaktiverad. En "Försök igen"-knapp finns bredvid.

### Promptprofiler

- **Aktiv profil** — Dropdown
- **Knappar** — Skapa ny, Ta bort (ej standardprofilen)
- **Textfält** — Redigera vald profils systemprompt
- **Standardprofil** — Kan redigeras men inte tas bort

Standard systemprompt:
> "Du är en textassistent. Användaren har dikterat en text och vill nu ändra den. Returnera BARA den redigerade texten, inget annat. Ingen förklaring, inga citattecken. Om användaren säger att du hörde fel, korrigera texten. Om användaren ger en redigeringsinstruktion, utför den."

### Mikrofon

| Inställning | Typ | Standard |
|---|---|---|
| Inspelningsenhet | Dropdown | Systemstandard |

### Ljud

| Inställning | Typ | Standard |
|---|---|---|
| Uppspelningsenhet | Dropdown | Systemstandard |
| Ljud vid inspelningsstart | Checkbox | På |
| Ljud vid transkribering klar | Checkbox | På |
| Volym | Slider | 70% |

### Notiser

| Inställning | Typ | Standard |
|---|---|---|
| Visa popup vid transkribering | Checkbox | På |
| Notis-varaktighet | Slider | 4 sek (2-10) |

### Övrigt

| Inställning | Typ | Standard |
|---|---|---|
| Max inspelningstid | Slider | 60 sek (10-120) |
| Autostart vid inloggning | Checkbox | Av |
| Max sparad historik | Dropdown | 500 (100/500/1000/obegränsad) |
| Rensa historik | Knapp | Bekräftelsedialog |

### Sparbeteende

Ändringar sparas automatiskt — ingen spara-knapp. Kort "Sparat!"-feedback vid ändring.

## Smart interpunktion

Post-processing av transkriberad text. Ersätter uttalade skiljetecken:

| Uttalat | Resultat |
|---|---|
| frågetecken | ? |
| utropstecken | ! |
| kommatecken | , |
| semikolon | ; |
| tre punkter | ... |
| ny rad / nyrad | \n (radbrytning) |
| ellips | ... |
| citattecken | " |

Mellanslag före skiljetecken rensas automatiskt.

## Installer

### Format

Fristående `.exe` via PyInstaller. Innehåller Python-runtime och alla beroenden. Användaren behöver inte installera Python.

### Installationsflöde

1. Dubbelklicka på `WhisperTyper-Setup.exe`
2. Välkomstskärm
3. Välj installationsplats (standard: `C:\Program Files\WhisperTyper`)
4. Installation pågår (progressbar)
5. Klart — skapa skrivbordsgenväg? Starta nu?

Whisper-modellen väljs inte i installern — den väljs i inställningarna vid första körning. Modellen laddas ned automatiskt vid behov (Whisper gör detta inbyggt). Detta håller installern enkel och `.exe`-filen mindre.

### Vad som ingår i `.exe`

- Python runtime
- Alla pip-paket (PySide6, torch, whisper, pyaudio, pynput, pyperclip, requests)
- ffmpeg
- Ljudeffekter och ikoner

Whisper-modellen ingår INTE — den laddas ned vid första körning baserat på vald modell i inställningarna. Vid första start visas en dialog: "Laddar ned Whisper-modell (medium, ~1.5 GB)... Detta sker bara en gång."

### Storlek

Uppskattad storlek: ~500MB (CPU-only torch) till ~1.5GB (torch+CUDA). Whisper-modellen ingår inte — den laddas ned separat vid första körning (medium ~1.5GB, large ~3GB).

### Utvecklarläge

`installera.bat` och `starta.bat` behålls för att kunna köra från källkod under utveckling.

## Plattform

- **Primär:** Windows 10/11
- **Framtida:** Linux och macOS stöds av PySide6 och pynput. Enda Windows-specifika funktionen är autostart (Startup-mappen). Installer byggs per plattform vid behov.

### Autostart (Windows-specifik)

Autostart implementeras genom att skapa/ta bort en genväg i Windows Startup-mappen (`shell:startup`). Denna metod kräver inga registry-ändringar och är enkel att avinstallera. På Linux/Mac implementeras autostart via plattformsspecifika mekanismer (`.desktop`-fil / Launch Agent) om/när de plattformarna stöds.

## Konfigurationsfiler

Alla sparas i `%APPDATA%/WhisperTyper/` (Windows) eller `~/.config/whispertyper/` (Linux/Mac):

- `config.json` — Alla inställningar
- `history.json` — Transkriberings­historik
- `prompts.json` — Promptprofiler

### Datascheman

**config.json:**
```json
{
  "whisper_model": "medium",
  "language": "sv",
  "hotkey_dictate": "F9",
  "hotkey_ai": "F10",
  "ai_provider": "ollama",
  "ollama_model": "mistral:7b",
  "cloud_provider": "openai",
  "cloud_model": "gpt-4o-mini",
  "cloud_api_key": "",
  "active_prompt_profile": "standard",
  "microphone": "default",
  "audio_output": "default",
  "sound_on_record_start": true,
  "sound_on_transcription_done": true,
  "sound_volume": 70,
  "show_notifications": true,
  "notification_duration_sec": 4,
  "max_record_sec": 60,
  "autostart": false,
  "max_history": 500
}
```

**history.json:**
```json
[
  {
    "id": "uuid-string",
    "text": "Hej, hur mår du?",
    "timestamp": "2026-03-13T13:42:00",
    "duration_sec": 2.1,
    "mode": "dictate",
    "ai_edited": false,
    "original_text": null
    // mode: "dictate" (F9) | "ai_edit" (F10, skapar ny post med redigerad text)
    // ai_edited: true om denna post skapats via AI-redigering
    // original_text: den ursprungliga texten före AI-redigering (null om dictate)
  }
]
```

**prompts.json:**
```json
{
  "profiles": [
    {
      "id": "standard",
      "name": "Standard",
      "system_prompt": "Du är en textassistent...",
      "deletable": false
    },
    {
      "id": "formal-email",
      "name": "Formellt mejl",
      "system_prompt": "Du är en textassistent. Gör texten formell...",
      "deletable": true
    }
  ]
}
```
