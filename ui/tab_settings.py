from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QCheckBox, QLineEdit, QTextEdit,
    QPlainTextEdit, QFrame, QScrollArea, QInputDialog, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout,
)
from PySide6.QtCore import Qt
import requests


class NoScrollComboBox(QComboBox):
    """QComboBox that ignores wheel events when not focused."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if not self.hasFocus():
            event.ignore()
        else:
            super().wheelEvent(event)


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


class SettingsTab(QWidget):
    from PySide6.QtCore import Signal
    profiles_changed = Signal()
    hotkey_changed = Signal()

    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("SettingsTab { background: white; }")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: white; }")

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
            "QTextEdit { background: white; border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px; }"
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

    # ── Helpers ──

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

    def _open_vocabulary_dialog(self):
        dialog = VocabularyDialog(self.config, self)
        dialog.exec()

    def _on_whisper_provider_changed(self, index):
        provider = self._whisper_provider_combo.itemData(index)
        self._save("whisper_provider", provider)
        self._update_whisper_provider_visibility()

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

    def _on_cloud_whisper_provider_changed(self, index):
        provider = self._cloud_whisper_combo.itemData(index)
        self._save("cloud_whisper_provider", provider)
        self._update_cloud_whisper_models()

    def _update_cloud_whisper_models(self):
        self._cloud_whisper_model_combo.clear()
        provider = self.config.get("cloud_whisper_provider")
        if provider == "groq":
            models = ["whisper-large-v3-turbo", "whisper-large-v3", "distil-whisper-large-v3-en"]
        else:
            models = ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
        current = self.config.get("cloud_whisper_model")
        for m in models:
            self._cloud_whisper_model_combo.addItem(m)
        idx = self._cloud_whisper_model_combo.findText(current)
        if idx >= 0:
            self._cloud_whisper_model_combo.setCurrentIndex(idx)

    def _update_device_note(self):
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except ImportError:
            has_cuda = False
        if not has_cuda:
            self._device_note.setText("(GPU kräver NVIDIA GPU + CUDA)")
        else:
            self._device_note.setText(f"(Aktiv: {self.engine.device.upper()})")

    def _save(self, key, value):
        self.config.set(key, value)

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

    def _on_provider_changed(self, index):
        provider = self._provider_combo.itemData(index)
        self._save("ai_provider", provider)
        self._update_provider_visibility()

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

    def _load_ollama_models(self):
        self._ollama_model_combo.clear()
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                models = r.json().get("models", [])
                if models:
                    current = self.config.get("ollama_model")
                    for m in models:
                        self._ollama_model_combo.addItem(m["name"])
                    idx = self._ollama_model_combo.findText(current)
                    if idx >= 0:
                        self._ollama_model_combo.setCurrentIndex(idx)
                    self._ollama_model_combo.setEnabled(True)
                    self._ollama_retry_btn.setVisible(False)
                    return
        except Exception:
            pass
        self._ollama_model_combo.addItem("Ollama ej tillgänglig — starta Ollama")
        self._ollama_model_combo.setEnabled(False)
        self._ollama_retry_btn.setVisible(True)

    def _save_api_key(self):
        key = self._api_key_input.text()
        provider = self.config.get("cloud_provider")
        self._save("cloud_api_key", key)
        self._save(f"cloud_api_key_{provider}", key)

    def _on_cloud_provider_changed(self, index):
        # Spara nuvarande nyckel till provider-specifikt fält
        old_provider = self.config.get("cloud_provider")
        current_key = self._api_key_input.text()
        if old_provider and current_key:
            self._save(f"cloud_api_key_{old_provider}", current_key)

        provider = self._cloud_provider_combo.itemData(index)
        self._save("cloud_provider", provider)
        self._update_cloud_models()

        # Ladda den nya providerns sparade nyckel
        saved_key = self.config.get(f"cloud_api_key_{provider}") or ""
        self._api_key_input.setText(saved_key)
        self._save("cloud_api_key", saved_key)

    def _update_cloud_models(self):
        self._cloud_model_combo.clear()
        provider = self.config.get("cloud_provider")
        if provider == "openai":
            models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
        elif provider == "groq":
            models = [
                "llama-3.1-8b-instant",
                "llama-3.3-70b-versatile",
                "meta-llama/llama-4-scout-17b-16e-instruct",
                "qwen/qwen3-32b",
                "moonshotai/kimi-k2-instruct",
            ]
        else:
            models = ["claude-haiku-3-5-20241022", "claude-sonnet-4-6-20250514", "claude-haiku-4-5-20251001"]
        current = self.config.get("cloud_model")
        for m in models:
            self._cloud_model_combo.addItem(m)
        idx = self._cloud_model_combo.findText(current)
        if idx >= 0:
            self._cloud_model_combo.setCurrentIndex(idx)

    def _update_prompt_combo(self):
        self._prompt_combo.blockSignals(True)
        self._prompt_combo.clear()
        active = self.config.get("active_prompt_profile")
        for i, p in enumerate(self.config.get_prompt_profiles()):
            self._prompt_combo.addItem(p["name"], p["id"])
            if p["id"] == active:
                self._prompt_combo.setCurrentIndex(i)
        self._prompt_combo.blockSignals(False)
        self._update_delete_btn()

    def _update_delete_btn(self):
        pid = self._prompt_combo.currentData()
        for p in self.config.get_prompt_profiles():
            if p["id"] == pid:
                self._del_profile_btn.setEnabled(p.get("deletable", True))
                return

    def _on_prompt_profile_changed(self, index):
        pid = self._prompt_combo.currentData()
        if pid:
            self.config.set("active_prompt_profile", pid)
            self._load_prompt_text()
            self._update_delete_btn()

    def _load_prompt_text(self):
        pid = self._prompt_combo.currentData()
        for p in self.config.get_prompt_profiles():
            if p["id"] == pid:
                self._prompt_edit.setPlainText(p["system_prompt"])
                self._auto_run_cb.setChecked(p.get("auto_run", False))
                return

    def _save_prompt(self):
        pid = self._prompt_combo.currentData()
        if pid:
            text = self._prompt_edit.toPlainText().strip()
            auto_run = self._auto_run_cb.isChecked()
            self.config.update_prompt_profile(pid, text, auto_run=auto_run)

    def _add_profile(self):
        name, ok = QInputDialog.getText(
            self, "Ny promptprofil", "Namn på profilen:"
        )
        if ok and name.strip():
            pid = name.strip().lower().replace(" ", "-")
            self.config.add_prompt_profile(pid, name.strip(), "")
            self._update_prompt_combo()
            # Select the new one
            idx = self._prompt_combo.findData(pid)
            if idx >= 0:
                self._prompt_combo.setCurrentIndex(idx)
            self.profiles_changed.emit()

    def _delete_profile(self):
        pid = self._prompt_combo.currentData()
        if not pid:
            return
        reply = QMessageBox.question(
            self,
            "Ta bort profil",
            f"Ta bort profilen?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.config.delete_prompt_profile(pid)
                self.config.set("active_prompt_profile", "standard")
                self._update_prompt_combo()
                self.profiles_changed.emit()
            except ValueError as e:
                QMessageBox.warning(self, "Fel", str(e))

    def _on_volume_changed(self, value):
        self._volume_label.setText(f"{value}%")
        self._save("sound_volume", value)

    def _on_notis_duration_changed(self, value):
        self._notis_label.setText(f"{value} sek")
        self._save("notification_duration_sec", value)

    def _on_max_record_changed(self, value):
        self._max_rec_label.setText(f"{value} sek")
        self._save("max_record_sec", value)


class KeyCaptureButton(QPushButton):
    """A button that captures the next key press as a hotkey."""

    from PySide6.QtCore import Signal as _Signal
    key_changed = _Signal(str)

    def __init__(self, current_key=""):
        super().__init__(current_key)
        self._capturing = False
        self.setMinimumWidth(100)
        self.setStyleSheet("""
            QPushButton { background: white; border: 1px solid #e0e0e0;
                          border-radius: 4px; padding: 6px 12px; }
            QPushButton:focus { border-color: #1976D2; }
        """)
        self.clicked.connect(self._start_capture)

    def _start_capture(self):
        self._capturing = True
        self.setText("Tryck en tangent...")
        self.setStyleSheet("""
            QPushButton { background: #e3f2fd; border: 1px solid #1976D2;
                          border-radius: 4px; padding: 6px 12px; color: #1976D2; }
        """)

    def keyPressEvent(self, event):
        if self._capturing:
            from PySide6.QtCore import Qt as QtKey
            key_code = event.key()

            modifier_keys = {QtKey.Key_Control, QtKey.Key_Shift, QtKey.Key_Alt, QtKey.Key_Meta}
            if key_code in modifier_keys:
                return

            key_map = {
                QtKey.Key_F1: "F1", QtKey.Key_F2: "F2", QtKey.Key_F3: "F3",
                QtKey.Key_F4: "F4", QtKey.Key_F5: "F5", QtKey.Key_F6: "F6",
                QtKey.Key_F7: "F7", QtKey.Key_F8: "F8", QtKey.Key_F9: "F9",
                QtKey.Key_F10: "F10", QtKey.Key_F11: "F11", QtKey.Key_F12: "F12",
                QtKey.Key_Escape: "Escape", QtKey.Key_Space: "Space",
                QtKey.Key_Return: "Return", QtKey.Key_Tab: "Tab",
            }

            parts = []
            mods = event.modifiers()
            if mods & QtKey.ControlModifier:
                parts.append("Ctrl")
            if mods & QtKey.AltModifier:
                parts.append("Alt")
            if mods & QtKey.ShiftModifier:
                parts.append("Shift")

            if key_code in key_map:
                key_str = key_map[key_code]
            elif event.text():
                key_str = event.text().upper()
            else:
                key_str = f"Key_{key_code}"
            parts.append(key_str)
            combo_str = "+".join(parts)

            self._capturing = False
            self.setText(combo_str)
            self.setStyleSheet("""
                QPushButton { background: white; border: 1px solid #e0e0e0;
                              border-radius: 4px; padding: 6px 12px; }
            """)
            self.key_changed.emit(combo_str)
        else:
            super().keyPressEvent(event)
