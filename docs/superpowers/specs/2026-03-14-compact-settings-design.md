# Kompakta inställningar — Designspecifikation

## Syfte

Gör inställningsfliken mer kompakt och användbar genom att:
- Minska 9 separata kort till 4 grupper med tunna avdelare
- Använda grid-layout för label+kontroll på samma rad
- Flytta ordlistan till en dialog
- Fixa scroll-hijacking på QComboBox-dropdowns

## Problem

1. **Lång scrollning** — 9 separata kort med ramar kräver scrollning
2. **Visuellt brus** — för många visuella element (ramar, sektionsrubriker, spacing)
3. **Scroll-hijacking** — QComboBox fångar wheel-events när musen råkar vara över en dropdown

## Design

### Layoutstruktur

Bort med `QFrame`-kort och `_card()`-metoden. Ersätt med:
- **Grupprubrik**: blå versaler, liten font, `letter-spacing: 0.5px`
- **Tunn avdelare**: `QFrame(HLine)` med 1px höjd mellan grupper
- **Grid-layout** inom varje grupp: labels ~110px, kontroller fyller resten
- **Tight spacing**: 4px vertikalt gap inom grupper, 12px mellan grupper

Scroll-area behålls som säkerhet men målet är att allt ryms utan scrollning.

### Gruppering (9 sektioner → 4 grupper)

#### 1. Transkribering
Sammanslår: Whisper + Ordlista

| Label | Kontroll |
|-------|----------|
| Provider | `QComboBox` — Lokal (Whisper) / Cloud |
| Modell | `QComboBox` — tiny/base/small/medium/large (lokal) eller cloud-modeller |
| Enhet | `QComboBox` — Auto/CPU/GPU (bara vid lokal) |
| Cloud-provider | `QComboBox` — Groq/OpenAI (bara vid cloud) |
| Språk | `QComboBox` — Svenska/Engelska/Auto-detect |
| Ordlista | `QPushButton` "Redigera…" → öppnar `QDialog` |

Villkorlig visning: Modell+Enhet visas vid lokal, Cloud-provider+Cloud-modell visas vid cloud. Samma logik som idag.

#### 2. AI-redigering
Sammanslår: AI-redigering + Promptprofiler

| Label | Kontroll |
|-------|----------|
| Provider | `QComboBox` — Lokal (Ollama) / Cloud |
| Ollama-modell | `QComboBox` + Retry-knapp (bara vid Ollama) |
| Cloud-provider | `QComboBox` — OpenAI/Anthropic/Groq (bara vid cloud) |
| Modell | `QComboBox` (bara vid cloud) |
| API-nyckel | `QLineEdit` password (bara vid cloud) |

Promptprofiler (under AI-inställningarna, ej i grid):
- **Rad**: `QComboBox` profil + "Ny"-länk + "Ta bort"-länk
- **Checkbox**: "Kör automatiskt på varje diktering"
- **QTextEdit**: Prompttext (kompakt, ~48px höjd)

Prompttext behålls inline — den är det mest använda inställningen.

#### 3. Kontroller
Sammanslår: Kortkommandon + Mikrofon + Max inspelningstid

| Label | Kontroll |
|-------|----------|
| Diktera | `KeyCaptureButton` |
| AI-redigering | `KeyCaptureButton` |
| Mikrofon | `QComboBox` |
| Max inspelningstid | `QSlider` + label (sek) |

#### 4. Ljud & Övrigt
Sammanslår: Ljud + Notiser + Övrigt

Checkboxar i en horisontell rad:
- ☑ Ljud vid start
- ☑ Ljud vid klar
- ☑ Popup-notis

| Label | Kontroll |
|-------|----------|
| Volym | `QSlider` + label (%) |
| Notisvaraktighet | `QSlider` + label (sek) |
| Max historik | `QComboBox` |

Sist:
- ☐ Autostart vid inloggning

### Ordlista-dialog

`VocabularyDialog(QDialog)`:
- **Titel**: "Ordlista"
- **Innehåll**: `QPlainTextEdit` med hint "Ett ord per rad"
- **Knappar**: Spara / Avbryt (`QDialogButtonBox`)
- Höjd: ~200px, bredd: ~300px

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
    label = QLabel(text)
    label.setStyleSheet(
        "color: #1976D2; font-size: 10px; font-weight: bold; "
        "text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;"
    )
    return label
```

### Avdelare

```python
def _separator(self):
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color: #eee;")
    line.setFixedHeight(1)
    return line
```

## Filer som ändras

| Fil | Ändring |
|-----|---------|
| `ui/tab_settings.py` | Fullständig omskrivning av `_setup_ui()`, ny `NoScrollComboBox`, ny `VocabularyDialog`, bort med `_card()` och `_section_label()` |

## Avgränsning

Följande ingår **inte**:
- Ändring av tray-menyn (redan kompakt)
- Ändring av Live- eller Historik-flikarna
- Ny funktionalitet — bara omorganisering av befintliga inställningar
- Ändringar i `config.py` eller `main.py`
