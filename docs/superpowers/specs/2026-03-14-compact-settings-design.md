# Kompakta inställningar — Designspecifikation

## Syfte

Gör inställningsfliken mer kompakt och användbar genom att:
- Minska 9 separata kort till 4 grupper med tunna avdelare
- Använda `QFormLayout` för label+kontroll på samma rad
- Flytta ordlistan till en dialog
- Fixa scroll-hijacking på QComboBox-dropdowns

## Problem

1. **Lång scrollning** — 9 separata kort med ramar kräver scrollning
2. **Visuellt brus** — för många visuella element (ramar, sektionsrubriker, spacing)
3. **Scroll-hijacking** — QComboBox fångar wheel-events när musen råkar vara över en dropdown

## Design

### Layoutstruktur

Bort med `QFrame`-kort och `_card()`-metoden. Ersätt med:
- **Grupprubrik**: blå versaler, liten font (versaler via `text.upper()` i Python — Qt QSS stödjer inte `text-transform`)
- **Tunn avdelare**: `QFrame(HLine)` med 1px höjd mellan grupper
- **`QFormLayout`** inom varje grupp: labels ~110px, kontroller fyller resten
- **Tight spacing**: 4px vertikalt gap inom grupper, 12px mellan grupper

Scroll-area behålls som säkerhet men målet är att allt ryms utan scrollning.

### Bevarade beteenden

Följande **måste** bevaras vid omskrivning:
- **Signaler**: `profiles_changed` och `hotkey_changed` — konsumeras av `dashboard.py` och `main.py`
- **Save-modell**: Combo/slider/checkbox sparar direkt via `config.set()`. Prompttext och ordlista sparas explicit via knapp/dialog.
- **`KeyCaptureButton`-klassen** — behålls oförändrad (separat widget)
- **Villkorlig visning**: `_update_provider_visibility()` och `_update_whisper_provider_visibility()` — samma logik, kan refaktoreras men beteendet bevaras
- **Hotkey-konfliktvarning**: `_hotkey_error` QLabel som visas vid dubblettbindningar
- **Enhetsnotering**: `_device_note` QLabel som visar GPU-status
- **Cloud-nyckelnotering**: "Använder API-nyckel från AI-inställningarna" vid cloud-transkribering
- **Dialoger**: `QInputDialog` vid ny profil, `QMessageBox.question` vid radering — bevaras

### Gruppering (9 sektioner → 4 grupper)

#### 1. Transkribering
Sammanslår: Whisper + Ordlista

| Label | Kontroll |
|-------|----------|
| Provider | `NoScrollComboBox` — Lokal (Whisper) / Cloud |
| Modell | `NoScrollComboBox` — tiny/base/small/medium/large (lokal) eller cloud-modeller |
| Enhet | `NoScrollComboBox` — Auto/CPU/GPU (bara vid lokal) + enhetsnotering |
| Cloud-provider | `NoScrollComboBox` — Groq/OpenAI (bara vid cloud) |
| Språk | `NoScrollComboBox` — Svenska/Engelska/Auto-detect |
| Ordlista | `QPushButton` "Redigera…" → öppnar `VocabularyDialog` |

Villkorlig visning: Modell+Enhet visas vid lokal, Cloud-provider+Cloud-modell visas vid cloud. Samma logik som idag.

Vid cloud visas även notering: "Använder API-nyckel från AI-inställningarna" (liten grå text).

#### 2. AI-redigering
Sammanslår: AI-redigering + Promptprofiler

| Label | Kontroll |
|-------|----------|
| Provider | `NoScrollComboBox` — Lokal (Ollama) / Cloud |
| Ollama-modell | `NoScrollComboBox` + Retry-knapp (bara vid Ollama) |
| Cloud-provider | `NoScrollComboBox` — OpenAI/Anthropic/Groq (bara vid cloud) |
| Modell | `NoScrollComboBox` (bara vid cloud) |
| API-nyckel | `QLineEdit` password (bara vid cloud) |

Promptprofiler (under AI-inställningarna, ej i form-layout):
- **Rad**: `NoScrollComboBox` profil + "Ny"-knapp + "Ta bort"-knapp (styling som idag: liten `QPushButton`)
- **Checkbox**: "Kör automatiskt på varje diktering"
- **QTextEdit**: Prompttext (~80px höjd, placeholder: `'Lämna tom för enkel korrigering, eller skriv en instruktion (t.ex. "Översätt till engelska")'`)
- **QPushButton**: "Spara prompt" (samma stil som idag)

#### 3. Kontroller
Sammanslår: Kortkommandon + Mikrofon + Max inspelningstid

| Label | Kontroll |
|-------|----------|
| Diktera | `KeyCaptureButton` |
| AI-redigering | `KeyCaptureButton` |
| Mikrofon | `NoScrollComboBox` |
| Max inspelningstid | `QSlider` + label (sek) |

Hotkey-konfliktvarning (`_hotkey_error` QLabel) visas under hotkey-raderna vid dubbletter.

#### 4. Ljud & Övrigt
Sammanslår: Ljud + Notiser + Övrigt

Checkboxar i en horisontell rad (`QHBoxLayout`):
- ☑ Ljud vid start
- ☑ Ljud vid klar
- ☑ Popup-notis

| Label | Kontroll |
|-------|----------|
| Volym | `QSlider` + label (%) |
| Notisvaraktighet | `QSlider` + label (sek) |
| Max historik | `NoScrollComboBox` |

Sist:
- ☐ Autostart vid inloggning

### Ordlista-dialog

`VocabularyDialog(QDialog)`:
- **Titel**: "Ordlista"
- **Innehåll**: `QPlainTextEdit` med hint "Ange ord som Whisper ska känna igen, ett per rad"
- **Knappar**: Spara / Avbryt (`QDialogButtonBox`)
- Höjd: ~200px, bredd: ~300px
- **Vid öppning**: laddar ord från `config.get_vocabulary()`
- **Vid Spara**: anropar `config.set_vocabulary(words)` och stänger dialogen
- **Vid Avbryt**: stänger utan att spara

### QComboBox scroll-fix

Subklassa `QComboBox` → `NoScrollComboBox`:

```python
class NoScrollComboBox(QComboBox):
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)
```

Alla `QComboBox` i `SettingsTab` ersätts med `NoScrollComboBox`.

### Grupprubrik-stil

```python
def _group_label(self, text):
    label = QLabel(text.upper())
    label.setStyleSheet(
        "color: #1976D2; font-size: 10px; font-weight: bold; margin-top: 4px;"
    )
    return label
```

### Avdelare

```python
def _separator(self):
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("background-color: #eee; border: none;")
    line.setFixedHeight(1)
    return line
```

## Filer som ändras

| Fil | Ändring |
|-----|---------|
| `ui/tab_settings.py` | Fullständig omskrivning av `_setup_ui()`, ny `NoScrollComboBox`, ny `VocabularyDialog`, bort med `_card()` och `_section_label()` — `KeyCaptureButton` bevaras oförändrad |

## Avgränsning

Följande ingår **inte**:
- Ändring av tray-menyn (redan kompakt)
- Ändring av Live- eller Historik-flikarna
- Ny funktionalitet — bara omorganisering av befintliga inställningar
- Ändringar i `config.py` eller `main.py`
