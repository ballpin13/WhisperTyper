# Promptprofiler 2.0 — Designspecifikation

## Bakgrund

Promptsystemet blandar idag output-formateringsregler med uppgiftsbeskrivning i en enda redigerbar text. Användaren måste veta att skriva "returnera BARA texten" i varje profil, annars klistras AI-kommentarer in i dokumentet.

Dessutom körs AI-steget bara manuellt (F10). Profiler som "Översätt till engelska" kräver att man trycker F10 varje gång — opraktiskt.

## Mål

1. **Separera bas-prompt från profilprompt** — output-regler bäddas in fast i koden, användaren skriver bara *vad* AI:n ska göra.
2. **Auto-körning** — valfri toggle per profil som kör AI-steget automatiskt på varje transkribering.

## Design

### Bas-systemprompt (fast, dold)

Alltid inkluderad, aldrig synlig för användaren:

```
Returnera ENBART den bearbetade texten.
Ingen förklaring, inga citattecken, inga inledande fraser, inget extra.
```

Denna bäddas in i `engine.py`, inte i profilen.

### Profilprompt (redigerbar)

Användarens instruktion för *vad* AI:n ska göra. Exempel:

| Profil | Profilprompt |
|--------|-------------|
| Standard | *(tom — ingen transformation, bara korrigeringsverktyg via F10)* |
| Översätt engelska | `Översätt texten till engelska.` |
| Formellt mejl | `Gör texten formell och professionell. Lägg till hälsningsfras och avslut.` |
| Mötesanteckningar | `Strukturera texten som mötesanteckningar med bullet points.` |

### Sammansättning

Bas-prompten och profilprompten kombineras till ett system-meddelande:

```
{bas-prompt}

{profilprompt}
```

Om profilprompten är tom skickas bara bas-prompten.

### Auto-körning

Nytt fält per profil: `auto_run` (boolean, default `false`).

| auto_run | Beteende |
|----------|----------|
| `false`  | Samma som idag. AI körs bara vid F10. |
| `true`   | Varje F9-transkribering skickas automatiskt genom AI:n innan den klistras in. |

### Flöden

**F9 med auto_run av (standard):**
```
Diktera → Whisper → smart_punctuation → klistra in
```

**F9 med auto_run på:**
```
Diktera → Whisper → smart_punctuation → AI-transformation → klistra in
```

AI-anropet i auto-läge:
- **System:** bas-prompt + profilprompt
- **User:** den transkriberade texten (bara texten, inget "Instruktion:"-format)

**F10 (manuell korrigering, oavsett auto_run):**
```
Diktera instruktion → Whisper → AI-redigering → ersätt text
```

AI-anropet vid F10:
- **System:** bas-prompt + profilprompt
- **User:** `Ursprunglig text: "X"\n\nInstruktion: Y` (samma som idag)

### State-hantering vid auto-körning

När auto-körning är aktiv:
- `last_dictated_text` sätts till den **transformerade** texten (det användaren ser)
- Historiken sparar: transformerad text som `text`, rå Whisper-output som `original_text`, mode `"auto_ai"`

Detta gör att F10-korrigeringar efter auto-körning opererar på den text som faktiskt klistrades in.

### Profildatamodell

```json
{
  "profiles": [
    {
      "id": "standard",
      "name": "Standard",
      "system_prompt": "",
      "auto_run": false,
      "deletable": false
    },
    {
      "id": "translate-en",
      "name": "Översätt engelska",
      "system_prompt": "Översätt texten till engelska.",
      "auto_run": true,
      "deletable": true
    }
  ]
}
```

`system_prompt` innehåller nu **bara** profilprompten (inte bas-prompten).

### Migrering

Vid uppstart: om en profils `system_prompt` innehåller den gamla DEFAULT_PROMPT-texten, ersätt med tom sträng. Lägg till `auto_run: false` om fältet saknas.

## UI-ändringar

### Inställningar-fliken

I prompt-sektionen:

1. **Profil-dropdown** — oförändrad
2. **Auto-körning checkbox** — `☐ Kör automatiskt på varje diktering`
   - Placeras direkt under dropdown, före textrutan
   - Tooltip: "AI-profilen körs automatiskt efter varje diktering istället för bara vid F10"
3. **Promptruta** — oförändrad, men placeholder-text: `Lämna tom för enkel korrigering via F10, eller skriv en instruktion (t.ex. "Översätt till engelska")`
4. **"Spara prompt"** — sparar nu även auto_run-värdet

### Tray-meny

Oförändrad — snabbväxling av profil fungerar som förut. Aktiv profils auto_run-status syns inte i menyn (onödig komplexitet).

### Live-fliken

Nuvarande profil-dropdown behålls. Ingen auto_run-indikator behövs här — användaren vet vilken profil som är aktiv.

## Kodändringar

### config.py

- `DEFAULT_PROMPT` → ta bort (eller behåll som `""`)
- Ny konstant: `BASE_SYSTEM_PROMPT` (fast bas-prompt)
- `get_active_prompt()` → returnerar **bara** profilprompten
- Ny: `get_active_auto_run()` → returnerar `bool`
- Ny: `get_full_system_prompt()` → returnerar `BASE_SYSTEM_PROMPT + "\n\n" + profilprompt` (eller bara bas om profilprompt är tom)
- Migreringskod i `get_prompt_profiles()` — lägger till `auto_run: false` om det saknas

### engine.py

- `_get_system_prompt()` → anropar `config.get_full_system_prompt()` istället
- I `_process_recording`, efter `mode == "dictate"` och `smart_punctuation`:
  - Kolla `self.config.get_active_auto_run()`
  - Om `true`: kör AI-transformation med ny metod `_ai_auto_transform(text)`
  - Ny signal: `auto_ai_started` / `auto_ai_done`
- `_ai_auto_transform(text)`:
  - Samma AI-anrop som `_ai_ollama`/`_ai_cloud` men med **bara texten** som user-meddelande (inget "Ursprunglig text / Instruktion"-format)

### tab_settings.py

- Lägg till `QCheckBox("Kör automatiskt på varje diktering")` i prompt-sektionen
- `_load_prompt_text()` → laddar även `auto_run`-checkbox
- `_save_prompt()` → sparar även `auto_run`-värdet

## Avgränsning

Följande ingår **inte** i denna iteration:

- Visuell auto_run-indikator i tray eller live-flik
- Villkorlig auto-körning (t.ex. "kör bara om texten är längre än X ord")
- Kedja av profiler (kör flera transformer i sekvens)
- Ångrande av auto-transformation i live-fliken
