# F10 AI-redigering — Redesign

## Bakgrund

F10 (AI-redigering) har flera kända problem som gör funktionen opålitlig:

1. **Oavsiktliga korta tryck** — ett snabbt tryck (<0.5s) ger Whisper tystnad/brus som kan hallucineras till påhittad text, vilken sedan skickas som AI-instruktion och ändrar användarens text.
2. **Inkonsekvent ersättning** — `_replace_last_text` kör alltid backspace × antal tecken utan att veta om cursor-positionen eller fönstret är rätt. Ibland ersätts texten korrekt, ibland skrivs ny text bredvid den gamla.
3. **F10 stjäl fokus** — F10 är menybar-tangenten i många Windows-program, vilket gör att det aktiva fönstret tappar fokus.
4. **Oklart vad som redigeras** — efter en misslyckad AI-redigering vet användaren inte om nästa F10-tryck redigerar originaltexten eller det felaktiga resultatet.
5. **Ctrl+V misslyckas ibland** — timing-problem i pynput gör att bara "v" skrivs istället för paste.

## Ändringar

### 1. Minimigräns för inspelning

Gäller både F9 och F10.

- Om inspelningen är kortare än **0.5 sekunder**, kassera den direkt utan att skicka till Whisper.
- Emit `error("Inspelning för kort")` så att Live-fliken visar kortvarigt statusmeddelande, sedan återgå till "Redo".
- Gränsen är hårdkodad — ingen inställning behövs.

**Implementation:** Varaktigheten beräknas i `_record_audio` men är inte tillgänglig i `_process_recording`. Lösning: spara varaktigheten som `self._last_recording_duration` i `_record_audio` (efter `duration = time.time() - start`). Kontrollera den i `_process_recording` innan Whisper-transkribering startar.

**Live-fliken (`tab_live.py`):** `_on_error` visar idag bara "Redo". Ändra så att felmeddelandet visas i statustexten i ~2 sekunder (via `QTimer.singleShot`), sedan återgå till "Redo".

### 2. Separerat text-state

Ersätt `last_typed_text` med tre separata fält:

| Fält | Sätts av | Syfte |
|---|---|---|
| `last_dictated_text` | F9 enbart | Originaltexten som AI:n alltid redigerar |
| `last_injected_text` | F9 och F10 | Texten som faktiskt finns i målfönstret just nu |
| `last_injected_window` | F9 och F10 | HWND för fönstret där texten klistrades in (0 på icke-Windows) |

**F9-flöde:**
1. Whisper transkriberar → smart interpunktion.
2. `_type_text(text)` klistrar in texten.
3. Sätter `last_dictated_text = text`, `last_injected_text = text`, `last_injected_window = <aktivt fönster>`.

**F10-flöde (hotkey):**
1. Whisper transkriberar instruktionen.
2. AI redigerar `last_dictated_text` (alltid originalet, aldrig föregående AI-resultat).
3. `_replace_last_text(new_text)` ersätter `last_injected_text` i målfönstret (se sektion 3).
4. Sätter `last_injected_text = new_text`, `last_injected_window = <aktivt fönster>`. `last_dictated_text` ändras **inte**.

**UI-triggrad AI-redigering (`ai_edit_text`-metoden):**
Anropas från Live-flikens "Redigera med AI"-knapp. Denna metod tar `original_text` som parameter (texten som visas i Live-fliken). Den ska:
- Använda `original_text` som den text AI:n redigerar (skickas i prompten).
- **Inte** ändra `last_dictated_text`, `last_injected_text` eller `last_injected_window` — UI-redigering påverkar bara historiken och Live-flikens visning, inte fönsterinjektionen.
- Returnera AI-resultatet som idag.

**Konsekvens:** Flera F10-tryck i rad redigerar alltid F9-originalet. En ny F9-diktering nollställer alla tre fält.

**Alla ställen `last_typed_text` refereras och vad de ska ändras till:**

| Plats | Nuvarande | Nytt fält |
|---|---|---|
| `engine.py` `__init__` | `self.last_typed_text = ""` | `self.last_dictated_text = ""`, `self.last_injected_text = ""`, `self.last_injected_window = 0`, `self._active_hotkey = None` |
| `engine.py` `_handle_ai_edit` check | `if not self.last_typed_text` | `if not self.last_dictated_text` |
| `engine.py` `_handle_ai_edit` emit+replace | `self.ai_done.emit(...)` sedan `self._replace_last_text(...)` | Byt ordning: kör `_replace_last_text(new_text)` **först**, sedan `ai_done.emit(self.last_dictated_text, new_text)` — så att state-fälten är uppdaterade innan signalen når UI:t |
| `engine.py` `_handle_ai_edit` history | `original_text=self.last_typed_text` | `original_text=self.last_dictated_text` (notera: alla kedjade F10 får samma `original_text` — detta är avsiktligt) |
| `engine.py` `_ai_ollama` prompt | `self.last_typed_text` | `self.last_dictated_text` |
| `engine.py` `_ai_cloud` prompt | `self.last_typed_text` | `self.last_dictated_text` |
| `engine.py` `_process_recording` (dictate) | *(ny rad)* | Lägg till `self.last_dictated_text = text` efter `_type_text(text)` |
| `engine.py` `_type_text` | `self.last_typed_text = text` | `self.last_injected_text = text` + sätt `last_injected_window` |
| `engine.py` `_replace_last_text` | `if self.last_typed_text` | `if self.last_injected_text` |
| `engine.py` `ai_edit_text` | `self.last_typed_text = original_text` | Ta bort — använd `original_text` direkt i prompten |
| `main.py` `_copy_last_text` | `self.engine.last_typed_text` | `self.engine.last_injected_text` |

### 3. Fönsterspårning och ersättningslogik

Använder `win32gui.GetForegroundWindow()` för att spåra aktivt fönster.

**Hjälpfunktion:**
```python
def _get_foreground_window(self):
    """Returnera aktivt fönsters HWND, eller 0 om win32gui inte finns."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return hwnd if hwnd else 0
    except ImportError:
        return 0
```

**Vid `_type_text`:**
- Anropa `_get_foreground_window()` *innan* clipboard-operationer och spara i `last_injected_window`.

**Vid `_replace_last_text` (ordning är kritisk):**
1. Spara nuvarande fönster: `current_window = self._get_foreground_window()`
2. Jämför `current_window` med `self.last_injected_window`:
   - **Samma fönster OCH båda != 0:** kör backspace × `len(self.last_injected_text)`, sedan anropa `_type_text(new_text)`.
   - **Annat fönster ELLER nollvärde:** skippa backspace, anropa `_type_text(new_text)` direkt.
3. `_type_text` uppdaterar `last_injected_text` och `last_injected_window` — detta är korrekt eftersom det nya fönstret nu har den nya texten.

**Backspace och radbrytningar:**
`len(last_injected_text)` räknar Python-tecken, men `\n` (radbrytning från smart interpunktion) kan kräva fler eller färre backspace beroende på målfönstret. Denna begränsning accepteras i denna iteration. En framtida förbättring kan använda select-all-paste istället (t.ex. markera texten med Shift+Home × antal rader, sedan klistra in). Radbrytningar från smart interpunktion (`ny rad`/`nyrad`) förekommer sällan i korta dikterade texter.

**Backspace-timing:**
Nuvarande kod skickar backspace i en tight loop. Lägg till `time.sleep(0.01)` var 20:e backspace för att undvika att överbelasta målappen vid längre texter.

**Fallback (icke-Windows / WSL2 utveckling):**
- Om `win32gui` inte kan importeras (Linux, Mac, WSL2), returnerar `_get_foreground_window()` alltid 0.
- Jämförelsen `0 == 0` med `both != 0`-villkoret innebär att det alltid behandlas som "annat fönster" → paste utan backspace.
- Detta är en känd begränsning under utveckling i WSL2. I produktion (Windows .exe via PyInstaller) fungerar fönsterspårning normalt.

**Beroende:** `pywin32` läggs till i `requirements.txt` med kommentar att det är Windows-only och optional.

### 4. Ctrl+V-stabilitet

**Problem:** `pynput`s `pressed(Ctrl)` + `tap("v")` kan misslyckas under load, och bara "v" skrivs.

**Fix i `_type_text`:**
```python
# Nuvarande (engine.py rad 361-362):
with self._kb_controller.pressed(pynput_keyboard.Key.ctrl):
    self._kb_controller.tap("v")

# Nytt:
with self._kb_controller.pressed(pynput_keyboard.Key.ctrl):
    time.sleep(0.05)  # Ge OS tid att registrera Ctrl-nedtryckning
    self._kb_controller.tap("v")
```

Den befintliga `time.sleep(0.05)` *före* `pressed(Ctrl)` (rad 360) finns kvar — den ger clipboard tid att uppdateras. Den nya sleep:en *inuti* blocket ger OS tid att registrera Ctrl som nedtryckt.

Öka fördröjningen efter paste från 0.15s till 0.2s för att ge målfönstret tid att processa clipboard.

### 5. Ny standard-hotkey: Ctrl+F9

**Motivering:** F10 är menybar-tangenten i Windows och stjäl fokus från aktiva program.

**Ändringar i `config.py`:**
- Byt `"hotkey_ai"` default från `"F10"` till `"ctrl+f9"`.
- Befintliga användare med `config.json` som redan har `"F10"` behåller det — `ConfigManager` laddar befintlig config och faller bara tillbaka till defaults för saknade nycklar.

**Ändringar i hotkey-lyssnaren (`engine.py`):**

Idag jämför lyssnaren enskilda tangenter. Ny logik med modifierarspårning:

**Parsning av hotkey-sträng:**
```python
def _parse_key(self, key_str):
    """Parsa 'ctrl+f9' → {'modifiers': {'ctrl'}, 'key': 'f9'} eller 'f9' → {'modifiers': set(), 'key': 'f9'}"""
    parts = key_str.lower().split("+")
    modifiers = set()
    key = parts[-1]  # Sista delen är alltid tangenten
    for p in parts[:-1]:
        if p in ("ctrl", "alt", "shift"):
            modifiers.add(p)
    return {"modifiers": modifiers, "key": key}
```

**Modifierarspårning:**
```python
def __init__(self, ...):
    self._active_modifiers = set()  # Spårar nedtryckta Ctrl/Alt/Shift

# I on_press:
def on_press(key):
    # Uppdatera modifierare
    if key in (pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
        self._active_modifiers.add("ctrl")
    elif key in (pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r, pynput_keyboard.Key.alt_gr):
        self._active_modifiers.add("alt")
    elif key in (pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
        self._active_modifiers.add("shift")

    # Matcha hotkeys
    normalized = self._normalize_key(key)  # Returnerar bara tangentnamnet, t.ex. "f9"
    if self.model is None or self._is_recording:
        return
    for hotkey_config, mode in [(dictate_parsed, "dictate"), (ai_parsed, "ai")]:
        if normalized == hotkey_config["key"] and self._active_modifiers == hotkey_config["modifiers"]:
            self._start_recording(mode)
            self._active_hotkey = hotkey_config["key"]  # Spara vilken tangent som startade inspelningen
            break

# I on_release:
def on_release(key):
    # Uppdatera modifierare
    if key in (pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
        self._active_modifiers.discard("ctrl")
    elif key in (pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r, pynput_keyboard.Key.alt_gr):
        self._active_modifiers.discard("alt")
    elif key in (pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
        self._active_modifiers.discard("shift")

    # Stoppa inspelning när huvudtangenten släpps (oavsett modifierare)
    normalized = self._normalize_key(key)
    if normalized == self._active_hotkey and self._is_recording:
        self._stop_recording()
        self._active_hotkey = None
```

**`_normalize_key` och modifierare:**
`_normalize_key` returnerar tangentnamn som `"f9"`, `"a"` etc. Den anropas *efter* modifierare redan hanterats i if/elif-kedjan. Om en modifierartangent (ctrl_l etc.) ändå når `_normalize_key` returneras `"ctrl_l"` — det matchar aldrig en `hotkey_config["key"]`, vilket är korrekt beteende (modifierare ska inte trigga hotkeys ensamma).

**Edge cases:**
- Ctrl släpps före F9: inspelning fortsätter tills F9 släpps (hold-to-record gäller huvudtangenten).
- F9 utan Ctrl: matchar diktering om diktering är konfigurerad som `"f9"` (inga modifierare). Matchar **inte** AI om AI är konfigurerad som `"ctrl+f9"`.
- Vänster-Ctrl och höger-Ctrl behandlas likadant (båda ger `"ctrl"`).

**Omstart av lyssnare vid hotkey-ändring:**
Idag startas `start_hotkey_listener()` en gång vid uppstart och läser hotkey-config vid det tillfället. Hotkey-ändring kräver omstart av lyssnaren. Lösning:
- Lägg till `restart_hotkey_listener()` som anropar `stop_hotkey_listener()` + `start_hotkey_listener()`.
- Lägg till signal `hotkey_changed = Signal()` i `SettingsTab` (samma mönster som `profiles_changed`).
- I `_save_hotkey`: efter `self.config.set(key, value)`, emit `self.hotkey_changed.emit()`.
- I `Dashboard`: koppla `self._settings_tab.hotkey_changed` + exponera som property.
- I `main.py`: koppla `self.dashboard.hotkey_changed.connect(self.engine.restart_hotkey_listener)`.

**Inställningar-UI — `KeyCaptureButton` (`tab_settings.py`):**

Uppdatera `keyPressEvent` för att fånga modifierare + tangent:

```python
def keyPressEvent(self, event):
    if self._capturing:
        key_code = event.key()

        # Ignorera ensamma modifierare
        modifier_keys = {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta}
        if key_code in modifier_keys:
            return  # Vänta på en riktig tangent

        # Bygg strängrepresentation
        parts = []
        mods = event.modifiers()
        if mods & Qt.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.AltModifier:
            parts.append("Alt")
        if mods & Qt.ShiftModifier:
            parts.append("Shift")

        # Tangentnamn (samma key_map som idag)
        key_str = key_map.get(key_code) or event.text().upper() or f"Key_{key_code}"
        parts.append(key_str)
        combo_str = "+".join(parts)  # T.ex. "Ctrl+F9"

        self._capturing = False
        self.setText(combo_str)
        # Återställ styling...
        self.key_changed.emit(combo_str)
```

Strängformatet `"Ctrl+F9"` är case-insensitive vid jämförelse — `_parse_key` gör `.lower()`.

## Berörda filer

| Fil | Ändring |
|---|---|
| `engine.py` | Minimigräns, text-state (3 fält), fönsterspårning, Ctrl+V-fix, hotkey-kombination med modifierare, `restart_hotkey_listener()` |
| `config.py` | Ny default för `hotkey_ai`: `"ctrl+f9"` |
| `main.py` | Byt `last_typed_text` → `last_injected_text`, koppla `hotkey_changed`-signal |
| `ui/tab_live.py` | `_on_error` visar felmeddelande temporärt (QTimer) |
| `ui/tab_settings.py` | `KeyCaptureButton` med modifierare, `hotkey_changed`-signal, anropa `restart_hotkey_listener` |
| `requirements.txt` | Lägg till `pywin32` (Windows-only, optional) |

## Beroenden

- `pywin32` — för `win32gui.GetForegroundWindow()`. Installeras via pip. Windows-only. Importeras med try/except för plattformsoberoende fallback. I WSL2-utvecklingsmiljö är den inte tillgänglig, vilket innebär att fönsterspårning alltid faller tillbaka till "klistra in utan backspace".

## Avgränsning

Följande ingår **inte** i denna iteration:
- Whisper-hallucinationsfiltrering (no_speech_probability) — framtida förbättring.
- Ångra-mekanism i WhisperTyper-UI — Ctrl+Z i målappen fungerar redan.
- Kedjad AI-redigering (redigera AI-resultatet) — kan övervägas framöver.
- Select-all-paste som alternativ till backspace-räkning — framtida förbättring om radbrytningar i dikterad text visar sig vara ett problem.
