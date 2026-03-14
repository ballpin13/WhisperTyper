# Compact Settings Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the settings tab from 9 card-based sections to 4 compact groups with grid layout, no scrolling, and fixed combo box scroll-hijacking.

**Architecture:** Single-file rewrite of `ui/tab_settings.py`. Add two small widget classes (`NoScrollComboBox`, `VocabularyDialog`), rewrite `_setup_ui()` to use `QFormLayout` groups with thin dividers, remove card/section helpers. All existing signals, save behavior, and helper methods preserved.

**Tech Stack:** PySide6 (Qt for Python)

**Spec:** `docs/superpowers/specs/2026-03-14-compact-settings-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `ui/tab_settings.py` | Modify | Complete rewrite of `_setup_ui()`, add `NoScrollComboBox` and `VocabularyDialog` classes, remove `_card()` and `_section_label()`, keep `KeyCaptureButton` and all helper methods unchanged |

---

## Chunk 1: Widget Classes + Layout Rewrite

### Task 1: Add NoScrollComboBox class

**Files:**
- Modify: `ui/tab_settings.py` (add class before `SettingsTab`)

- [ ] **Step 1: Add NoScrollComboBox class at top of file (after imports, before SettingsTab)**

```python
class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events when not focused."""
    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)
```

- [ ] **Step 2: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: add NoScrollComboBox to prevent scroll hijacking"
```

---

### Task 2: Add VocabularyDialog class

**Files:**
- Modify: `ui/tab_settings.py` (add class after `NoScrollComboBox`, before `SettingsTab`)

- [ ] **Step 1: Add VocabularyDialog class**

```python
class VocabularyDialog(QDialog):
    """Modal dialog for editing the vocabulary word list."""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Ordlista")
        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)

        hint = QLabel("Ange ord som Whisper ska känna igen, ett per rad")
        hint.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(hint)

        self._edit = QPlainTextEdit()
        self._edit.setPlainText("\n".join(config.get_vocabulary()))
        layout.addWidget(self._edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Spara")
        buttons.button(QDialogButtonBox.Cancel).setText("Avbryt")
        buttons.accepted.connect(self._save_and_close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save_and_close(self):
        text = self._edit.toPlainText()
        words = [w.strip() for w in text.splitlines() if w.strip()]
        self.config.set_vocabulary(words)
        self.accept()
```

- [ ] **Step 2: Add QDialog and QDialogButtonBox to imports**

Update the imports at top of file — add `QDialog` and `QDialogButtonBox`:

```python
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QCheckBox, QLineEdit, QTextEdit,
    QPlainTextEdit, QFrame, QScrollArea, QInputDialog, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout,
)
```

Note: also add `QFormLayout` here since it's needed for Task 3.

- [ ] **Step 3: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: add VocabularyDialog for compact vocabulary editing"
```

---

### Task 3: Rewrite _setup_ui — helper methods + scroll container

**Files:**
- Modify: `ui/tab_settings.py` — `SettingsTab._setup_ui()` and helper methods

- [ ] **Step 1: Replace `_section_label()` and `_card()` with `_group_label()` and `_separator()`**

Delete `_section_label()` (lines 539-543) and `_card()` (lines 545-550). Add:

```python
def _group_label(self, text):
    label = QLabel(text.upper())
    label.setStyleSheet(
        "color: #1976D2; font-size: 10px; font-weight: bold; margin-top: 4px;"
    )
    return label

def _separator(self):
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("background-color: #eee; border: none;")
    line.setFixedHeight(1)
    return line
```

- [ ] **Step 2: Do NOT rewrite `_setup_ui()` yet** — the group builder methods (Tasks 4–7) must exist first. Continue to Task 4.

---

### Task 4: Build Group 1 — Transkribering

**Files:**
- Modify: `ui/tab_settings.py` — add `_build_group_transcription()` method

- [ ] **Step 1: Write `_build_group_transcription()`**

```python
def _build_group_transcription(self, parent_layout):
    parent_layout.addWidget(self._group_label("Transkribering"))
    form = QFormLayout()
    form.setSpacing(4)

    # Provider
    self._whisper_provider_combo = NoScrollComboBox()
    self._whisper_provider_combo.addItem("Lokal (Whisper)", "local")
    self._whisper_provider_combo.addItem("Cloud", "cloud")
    current_wp = self.config.get("whisper_provider")
    for i in range(self._whisper_provider_combo.count()):
        if self._whisper_provider_combo.itemData(i) == current_wp:
            self._whisper_provider_combo.setCurrentIndex(i)
    self._whisper_provider_combo.currentIndexChanged.connect(self._on_whisper_provider_changed)
    form.addRow("Provider:", self._whisper_provider_combo)

    # Local: Model
    self._model_combo = NoScrollComboBox()
    for m in ["tiny", "base", "small", "medium", "large"]:
        self._model_combo.addItem(m)
    self._model_combo.setCurrentText(self.config.get("whisper_model"))
    self._model_combo.currentTextChanged.connect(lambda v: self._save("whisper_model", v))
    self._model_label = QLabel("Modell:")
    form.addRow(self._model_label, self._model_combo)

    # Local: Device
    self._device_combo = NoScrollComboBox()
    self._device_combo.addItem("Auto", "auto")
    self._device_combo.addItem("CPU", "cpu")
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            self._device_combo.addItem(f"GPU ({gpu_name})", "cuda")
    except ImportError:
        pass
    current_device = self.config.get("whisper_device")
    for i in range(self._device_combo.count()):
        if self._device_combo.itemData(i) == current_device:
            self._device_combo.setCurrentIndex(i)
    self._device_combo.currentIndexChanged.connect(
        lambda i: self._save("whisper_device", self._device_combo.itemData(i))
    )
    self._device_row = QWidget()
    device_row_layout = QHBoxLayout(self._device_row)
    device_row_layout.setContentsMargins(0, 0, 0, 0)
    device_row_layout.addWidget(self._device_combo)
    self._device_note = QLabel("")
    self._device_note.setStyleSheet("color: #666; font-size: 11px;")
    self._update_device_note()
    device_row_layout.addWidget(self._device_note)
    device_row_layout.addStretch()
    self._device_label = QLabel("Enhet:")
    form.addRow(self._device_label, self._device_row)

    # Cloud: Provider
    self._cloud_whisper_combo = NoScrollComboBox()
    self._cloud_whisper_combo.addItem("Groq (gratis)", "groq")
    self._cloud_whisper_combo.addItem("OpenAI", "openai")
    current_cwp = self.config.get("cloud_whisper_provider")
    for i in range(self._cloud_whisper_combo.count()):
        if self._cloud_whisper_combo.itemData(i) == current_cwp:
            self._cloud_whisper_combo.setCurrentIndex(i)
    self._cloud_whisper_combo.currentIndexChanged.connect(self._on_cloud_whisper_provider_changed)
    self._cloud_whisper_label = QLabel("Cloud-provider:")
    form.addRow(self._cloud_whisper_label, self._cloud_whisper_combo)

    # Cloud: Model
    self._cloud_whisper_model_combo = NoScrollComboBox()
    self._update_cloud_whisper_models()
    self._cloud_whisper_model_combo.currentTextChanged.connect(
        lambda v: self._save("cloud_whisper_model", v)
    )
    self._cloud_whisper_model_label = QLabel("Cloud-modell:")
    form.addRow(self._cloud_whisper_model_label, self._cloud_whisper_model_combo)

    # Cloud: key note
    self._whisper_cloud_key_note_label = QLabel("")
    self._whisper_cloud_key_note = QLabel("Använder API-nyckel från AI-inställningarna")
    self._whisper_cloud_key_note.setStyleSheet("color: #666; font-size: 11px;")
    form.addRow(self._whisper_cloud_key_note_label, self._whisper_cloud_key_note)

    # Language (shared)
    self._lang_combo = NoScrollComboBox()
    self._lang_combo.addItem("Svenska", "sv")
    self._lang_combo.addItem("Engelska", "en")
    self._lang_combo.addItem("Auto-detect", "auto")
    current_lang = self.config.get("language")
    for i in range(self._lang_combo.count()):
        if self._lang_combo.itemData(i) == current_lang:
            self._lang_combo.setCurrentIndex(i)
    self._lang_combo.currentIndexChanged.connect(
        lambda i: self._save("language", self._lang_combo.itemData(i))
    )
    form.addRow("Språk:", self._lang_combo)

    # Vocabulary button
    vocab_btn = QPushButton("Redigera…")
    vocab_btn.setStyleSheet(
        "QPushButton { padding: 4px 12px; font-size: 11px; }"
    )
    vocab_btn.clicked.connect(self._open_vocabulary_dialog)
    form.addRow("Ordlista:", vocab_btn)

    parent_layout.addLayout(form)
    self._update_whisper_provider_visibility()
```

- [ ] **Step 2: Add `_open_vocabulary_dialog()` helper and update `_update_whisper_provider_visibility()`**

```python
def _open_vocabulary_dialog(self):
    dialog = VocabularyDialog(self.config, self)
    dialog.exec()
```

Update `_update_whisper_provider_visibility()` to control the new label references:

```python
def _update_whisper_provider_visibility(self):
    is_local = self.config.get("whisper_provider") == "local"
    # Local-only widgets
    self._model_label.setVisible(is_local)
    self._model_combo.setVisible(is_local)
    self._device_label.setVisible(is_local)
    self._device_row.setVisible(is_local)
    # Cloud-only widgets
    self._cloud_whisper_label.setVisible(not is_local)
    self._cloud_whisper_combo.setVisible(not is_local)
    self._cloud_whisper_model_label.setVisible(not is_local)
    self._cloud_whisper_model_combo.setVisible(not is_local)
    self._whisper_cloud_key_note_label.setVisible(not is_local)
    self._whisper_cloud_key_note.setVisible(not is_local)
```

- [ ] **Step 3: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: build compact Transkribering group"
```

---

### Task 5: Build Group 2 — AI-redigering

**Files:**
- Modify: `ui/tab_settings.py` — add `_build_group_ai()` method

- [ ] **Step 1: Write `_build_group_ai()`**

```python
def _build_group_ai(self, parent_layout):
    parent_layout.addWidget(self._group_label("AI-redigering"))
    form = QFormLayout()
    form.setSpacing(4)

    # Provider
    self._provider_combo = NoScrollComboBox()
    self._provider_combo.addItem("Lokal (Ollama)", "ollama")
    self._provider_combo.addItem("Cloud", "cloud")
    current_provider = self.config.get("ai_provider")
    for i in range(self._provider_combo.count()):
        if self._provider_combo.itemData(i) == current_provider:
            self._provider_combo.setCurrentIndex(i)
    self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
    form.addRow("Provider:", self._provider_combo)

    # Ollama model + retry
    ollama_widget = QWidget()
    ollama_layout = QHBoxLayout(ollama_widget)
    ollama_layout.setContentsMargins(0, 0, 0, 0)
    self._ollama_model_combo = NoScrollComboBox()
    self._ollama_model_combo.setMinimumWidth(200)
    self._ollama_retry_btn = QPushButton("Försök igen")
    self._ollama_retry_btn.setStyleSheet("QPushButton { padding: 4px 8px; font-size: 11px; }")
    self._ollama_retry_btn.clicked.connect(self._load_ollama_models)
    self._load_ollama_models()
    self._ollama_model_combo.currentTextChanged.connect(lambda v: self._save("ollama_model", v))
    ollama_layout.addWidget(self._ollama_model_combo)
    ollama_layout.addWidget(self._ollama_retry_btn)
    ollama_layout.addStretch()
    self._ollama_row_widget = ollama_widget
    self._ollama_row_label = QLabel("Ollama-modell:")
    form.addRow(self._ollama_row_label, self._ollama_row_widget)

    # Cloud provider
    self._cloud_provider_combo = NoScrollComboBox()
    self._cloud_provider_combo.addItem("OpenAI", "openai")
    self._cloud_provider_combo.addItem("Anthropic", "anthropic")
    self._cloud_provider_combo.addItem("Groq", "groq")
    current_cp = self.config.get("cloud_provider")
    for i in range(self._cloud_provider_combo.count()):
        if self._cloud_provider_combo.itemData(i) == current_cp:
            self._cloud_provider_combo.setCurrentIndex(i)
    self._cloud_provider_combo.currentIndexChanged.connect(self._on_cloud_provider_changed)
    self._cloud_provider_label = QLabel("Cloud-provider:")
    form.addRow(self._cloud_provider_label, self._cloud_provider_combo)

    # Cloud model
    self._cloud_model_combo = NoScrollComboBox()
    self._update_cloud_models()
    self._cloud_model_combo.currentTextChanged.connect(lambda v: self._save("cloud_model", v))
    self._cloud_model_label = QLabel("Modell:")
    form.addRow(self._cloud_model_label, self._cloud_model_combo)

    # API key
    self._api_key_input = QLineEdit()
    self._api_key_input.setEchoMode(QLineEdit.Password)
    _cp = self.config.get("cloud_provider")
    _saved = self.config.get(f"cloud_api_key_{_cp}") or self.config.get("cloud_api_key")
    self._api_key_input.setText(_saved or "")
    self._api_key_input.setMinimumWidth(250)
    self._api_key_input.editingFinished.connect(self._save_api_key)
    self._api_key_label = QLabel("API-nyckel:")
    form.addRow(self._api_key_label, self._api_key_input)

    parent_layout.addLayout(form)

    # Prompt profiles (not in form layout)
    row = QHBoxLayout()
    row.addWidget(QLabel("Profil:"))
    self._prompt_combo = NoScrollComboBox()
    self._add_profile_btn = QPushButton("Skapa ny")
    self._add_profile_btn.setStyleSheet("QPushButton { padding: 4px 12px; font-size: 11px; }")
    self._add_profile_btn.clicked.connect(self._add_profile)
    self._del_profile_btn = QPushButton("Ta bort")
    self._del_profile_btn.setStyleSheet(
        "QPushButton { padding: 4px 12px; font-size: 11px; color: #c62828; }"
    )
    self._del_profile_btn.clicked.connect(self._delete_profile)
    self._update_prompt_combo()
    self._prompt_combo.currentIndexChanged.connect(self._on_prompt_profile_changed)
    row.addWidget(self._prompt_combo)
    row.addWidget(self._add_profile_btn)
    row.addWidget(self._del_profile_btn)
    row.addStretch()
    parent_layout.addLayout(row)

    self._auto_run_cb = QCheckBox("Kör automatiskt på varje diktering")
    self._auto_run_cb.setToolTip(
        "AI-profilen körs automatiskt efter varje diktering istället för bara vid AI-redigering"
    )
    parent_layout.addWidget(self._auto_run_cb)

    self._prompt_edit = QTextEdit()
    self._prompt_edit.setMaximumHeight(80)
    self._prompt_edit.setPlaceholderText(
        'Lämna tom för enkel korrigering, eller skriv en instruktion (t.ex. "Översätt till engelska")'
    )
    self._prompt_edit.setStyleSheet(
        "QTextEdit { border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px; }"
    )
    self._load_prompt_text()
    parent_layout.addWidget(self._prompt_edit)

    save_prompt_btn = QPushButton("Spara prompt")
    save_prompt_btn.setStyleSheet("""
        QPushButton { background: #e3f2fd; color: #1976D2; border: none;
                      border-radius: 6px; padding: 6px 16px; font-size: 12px; }
        QPushButton:hover { background: #bbdefb; }
    """)
    save_prompt_btn.clicked.connect(self._save_prompt)
    parent_layout.addWidget(save_prompt_btn, alignment=Qt.AlignLeft)

    self._update_provider_visibility()
```

- [ ] **Step 2: Update `_update_provider_visibility()` for new label references**

```python
def _update_provider_visibility(self):
    is_ollama = self.config.get("ai_provider") == "ollama"
    self._ollama_row_widget.setVisible(is_ollama)
    self._ollama_row_label.setVisible(is_ollama)
    self._cloud_provider_label.setVisible(not is_ollama)
    self._cloud_provider_combo.setVisible(not is_ollama)
    self._cloud_model_label.setVisible(not is_ollama)
    self._cloud_model_combo.setVisible(not is_ollama)
    self._api_key_label.setVisible(not is_ollama)
    self._api_key_input.setVisible(not is_ollama)
```

- [ ] **Step 3: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: build compact AI-redigering group"
```

---

### Task 6: Build Group 3 — Kontroller

**Files:**
- Modify: `ui/tab_settings.py` — add `_build_group_controls()` method

- [ ] **Step 1: Write `_build_group_controls()`**

```python
def _build_group_controls(self, parent_layout):
    parent_layout.addWidget(self._group_label("Kontroller"))
    form = QFormLayout()
    form.setSpacing(4)

    # Hotkeys
    self._hotkey_dictate = KeyCaptureButton(self.config.get("hotkey_dictate"))
    self._hotkey_dictate.key_changed.connect(lambda k: self._save_hotkey("hotkey_dictate", k))
    form.addRow("Diktera:", self._hotkey_dictate)

    self._hotkey_ai = KeyCaptureButton(self.config.get("hotkey_ai"))
    self._hotkey_ai.key_changed.connect(lambda k: self._save_hotkey("hotkey_ai", k))
    form.addRow("AI-redigering:", self._hotkey_ai)

    # Hotkey error (explicit label to avoid orphan gap when hidden)
    self._hotkey_error_label = QLabel("")
    self._hotkey_error_label.setVisible(False)
    self._hotkey_error = QLabel("")
    self._hotkey_error.setStyleSheet("color: #c62828; font-size: 11px;")
    self._hotkey_error.setVisible(False)
    form.addRow(self._hotkey_error_label, self._hotkey_error)

    # Microphone
    self._mic_combo = NoScrollComboBox()
    self._mic_combo.addItem("Systemstandard", "default")
    for mic in self.engine.get_microphones():
        self._mic_combo.addItem(mic["name"], str(mic["index"]))
    current_mic = self.config.get("microphone")
    for i in range(self._mic_combo.count()):
        if self._mic_combo.itemData(i) == current_mic:
            self._mic_combo.setCurrentIndex(i)
    self._mic_combo.currentIndexChanged.connect(
        lambda i: self._save("microphone", self._mic_combo.itemData(i))
    )
    form.addRow("Mikrofon:", self._mic_combo)

    # Max recording time
    rec_widget = QWidget()
    rec_layout = QHBoxLayout(rec_widget)
    rec_layout.setContentsMargins(0, 0, 0, 0)
    self._max_rec_slider = QSlider(Qt.Horizontal)
    self._max_rec_slider.setRange(10, 120)
    self._max_rec_slider.setValue(self.config.get("max_record_sec"))
    self._max_rec_label = QLabel(f"{self.config.get('max_record_sec')} sek")
    self._max_rec_slider.valueChanged.connect(self._on_max_record_changed)
    rec_layout.addWidget(self._max_rec_slider)
    rec_layout.addWidget(self._max_rec_label)
    form.addRow("Max inspelningstid:", rec_widget)

    parent_layout.addLayout(form)
```

- [ ] **Step 2: Update `_save_hotkey()` to also toggle the error label**

```python
def _save_hotkey(self, key, value):
    other_key = "hotkey_ai" if key == "hotkey_dictate" else "hotkey_dictate"
    other_value = self.config.get(other_key)
    if value.lower() == other_value.lower():
        self._hotkey_error.setText(
            f"Konflikt: {value} används redan för den andra funktionen."
        )
        self._hotkey_error.setVisible(True)
        self._hotkey_error_label.setVisible(True)
        return
    self._hotkey_error.setVisible(False)
    self._hotkey_error_label.setVisible(False)
    self.config.set(key, value)
    self.hotkey_changed.emit()
```

- [ ] **Step 3: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: build compact Kontroller group"
```

---

### Task 7: Build Group 4 — Ljud & Övrigt

**Files:**
- Modify: `ui/tab_settings.py` — add `_build_group_sound()` method

- [ ] **Step 1: Write `_build_group_sound()`**

```python
def _build_group_sound(self, parent_layout):
    parent_layout.addWidget(self._group_label("Ljud & Övrigt"))

    # Checkboxes in horizontal row
    cb_row = QHBoxLayout()
    self._sound_start_cb = QCheckBox("Ljud vid start")
    self._sound_start_cb.setChecked(self.config.get("sound_on_record_start"))
    self._sound_start_cb.toggled.connect(lambda v: self._save("sound_on_record_start", v))
    cb_row.addWidget(self._sound_start_cb)

    self._sound_done_cb = QCheckBox("Ljud vid klar")
    self._sound_done_cb.setChecked(self.config.get("sound_on_transcription_done"))
    self._sound_done_cb.toggled.connect(lambda v: self._save("sound_on_transcription_done", v))
    cb_row.addWidget(self._sound_done_cb)

    self._notis_cb = QCheckBox("Popup-notis")
    self._notis_cb.setChecked(self.config.get("show_notifications"))
    self._notis_cb.toggled.connect(lambda v: self._save("show_notifications", v))
    cb_row.addWidget(self._notis_cb)

    cb_row.addStretch()
    parent_layout.addLayout(cb_row)

    # Form for sliders and remaining controls
    form = QFormLayout()
    form.setSpacing(4)

    # Volume
    vol_widget = QWidget()
    vol_layout = QHBoxLayout(vol_widget)
    vol_layout.setContentsMargins(0, 0, 0, 0)
    self._volume_slider = QSlider(Qt.Horizontal)
    self._volume_slider.setRange(0, 100)
    self._volume_slider.setValue(self.config.get("sound_volume"))
    self._volume_label = QLabel(f"{self.config.get('sound_volume')}%")
    self._volume_slider.valueChanged.connect(self._on_volume_changed)
    vol_layout.addWidget(self._volume_slider)
    vol_layout.addWidget(self._volume_label)
    form.addRow("Volym:", vol_widget)

    # Notification duration
    notis_widget = QWidget()
    notis_layout = QHBoxLayout(notis_widget)
    notis_layout.setContentsMargins(0, 0, 0, 0)
    self._notis_slider = QSlider(Qt.Horizontal)
    self._notis_slider.setRange(2, 10)
    self._notis_slider.setValue(self.config.get("notification_duration_sec"))
    self._notis_label = QLabel(f"{self.config.get('notification_duration_sec')} sek")
    self._notis_slider.valueChanged.connect(self._on_notis_duration_changed)
    notis_layout.addWidget(self._notis_slider)
    notis_layout.addWidget(self._notis_label)
    form.addRow("Notisvaraktighet:", notis_widget)

    # Max history
    self._max_history_combo = NoScrollComboBox()
    for label, val in [("100", 100), ("500", 500), ("1000", 1000), ("Obegränsad", 0)]:
        self._max_history_combo.addItem(label, val)
    current_max = self.config.get("max_history")
    for i in range(self._max_history_combo.count()):
        if self._max_history_combo.itemData(i) == current_max:
            self._max_history_combo.setCurrentIndex(i)
    self._max_history_combo.currentIndexChanged.connect(
        lambda i: self._save("max_history", self._max_history_combo.itemData(i))
    )
    form.addRow("Max historik:", self._max_history_combo)

    parent_layout.addLayout(form)

    # Autostart checkbox
    self._autostart_cb = QCheckBox("Autostart vid inloggning")
    self._autostart_cb.setChecked(self.config.get("autostart"))
    self._autostart_cb.toggled.connect(lambda v: self._save("autostart", v))
    parent_layout.addWidget(self._autostart_cb)
```

- [ ] **Step 2: Commit**

```bash
git add ui/tab_settings.py
git commit -m "feat: build compact Ljud & Övrigt group"
```

---

### Task 8: Rewrite _setup_ui and clean up old code

**Files:**
- Modify: `ui/tab_settings.py`

- [ ] **Step 1: Rewrite `_setup_ui()` to use the 4 group builders**

Replace the entire `_setup_ui()` method body:

```python
def _setup_ui(self):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea { border: none; }")

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(4)

    self._build_group_transcription(layout)
    layout.addWidget(self._separator())
    self._build_group_ai(layout)
    layout.addWidget(self._separator())
    self._build_group_controls(layout)
    layout.addWidget(self._separator())
    self._build_group_sound(layout)

    layout.addStretch()
    scroll.setWidget(container)
    main_layout = QVBoxLayout(self)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.addWidget(scroll)
```

- [ ] **Step 2: Delete old methods and unused imports**

Remove these methods (now handled by new code):
- `_save_vocabulary()` — moved to `VocabularyDialog._save_and_close()`
- `_section_label()` — replaced by `_group_label()`
- `_card()` — no longer needed

Remove unused import: `from PySide6.QtGui import QFont` (was only used by `_section_label`).

- [ ] **Step 2: Run the app to verify**

```bash
cd /home/rober/Projects/Whisper && python main.py
```

Verify:
- Settings tab shows 4 compact groups
- All dropdowns work and don't scroll-hijack
- Vocabulary "Redigera…" button opens dialog
- Prompt profiles work (create, delete, save)
- Hotkey conflict detection works
- All checkboxes, sliders save correctly
- Cloud/local provider switching shows/hides correct fields
- No scrolling needed (or minimal)

- [ ] **Step 3: Commit**

```bash
git add ui/tab_settings.py
git commit -m "refactor: remove old card-based settings helpers"
```

---

### Task 9: Push to git for Windows testing

- [ ] **Step 1: Push changes**

```bash
git push
```

- [ ] **Step 2: Test on Windows**

User tests the app on Windows to verify the compact layout looks correct and all settings work.
