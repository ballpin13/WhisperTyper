from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSlider, QCheckBox, QLineEdit, QTextEdit,
    QFrame, QScrollArea, QInputDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont
import requests


class SettingsTab(QWidget):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self._setup_ui()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # ── Whisper ──
        layout.addWidget(self._section_label("Whisper"))
        whisper_frame = self._card()
        wl = QVBoxLayout(whisper_frame)

        # Model
        row = QHBoxLayout()
        row.addWidget(QLabel("Modell:"))
        self._model_combo = QComboBox()
        for m in ["tiny", "base", "small", "medium", "large"]:
            self._model_combo.addItem(m)
        self._model_combo.setCurrentText(self.config.get("whisper_model"))
        self._model_combo.currentTextChanged.connect(
            lambda v: self._save("whisper_model", v)
        )
        row.addWidget(self._model_combo)
        row.addStretch()
        wl.addLayout(row)

        # Language
        row = QHBoxLayout()
        row.addWidget(QLabel("Spr\u00e5k:"))
        self._lang_combo = QComboBox()
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
        row.addWidget(self._lang_combo)
        row.addStretch()
        wl.addLayout(row)

        # Device
        row = QHBoxLayout()
        row.addWidget(QLabel("Enhet:"))
        self._device_combo = QComboBox()
        self._device_combo.addItem("Auto", "auto")
        self._device_combo.addItem("CPU", "cpu")
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                self._device_combo.addItem(f"GPU ({gpu_name})", "cuda")
        except ImportError:
            pass  # torch not installed, CUDA option not available
        current_device = self.config.get("whisper_device")
        for i in range(self._device_combo.count()):
            if self._device_combo.itemData(i) == current_device:
                self._device_combo.setCurrentIndex(i)
        self._device_combo.currentIndexChanged.connect(
            lambda i: self._save("whisper_device", self._device_combo.itemData(i))
        )
        row.addWidget(self._device_combo)
        self._device_note = QLabel("")
        self._device_note.setStyleSheet("color: #666; font-size: 11px;")
        self._update_device_note()
        row.addWidget(self._device_note)
        row.addStretch()
        wl.addLayout(row)

        layout.addWidget(whisper_frame)

        # ── Kortkommandon ──
        layout.addWidget(self._section_label("Kortkommandon"))
        hotkey_frame = self._card()
        hl = QVBoxLayout(hotkey_frame)

        row = QHBoxLayout()
        row.addWidget(QLabel("Diktera:"))
        self._hotkey_dictate = KeyCaptureButton(self.config.get("hotkey_dictate"))
        self._hotkey_dictate.key_changed.connect(
            lambda k: self._save_hotkey("hotkey_dictate", k)
        )
        row.addWidget(self._hotkey_dictate)
        row.addStretch()
        hl.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("AI-redigering:"))
        self._hotkey_ai = KeyCaptureButton(self.config.get("hotkey_ai"))
        self._hotkey_ai.key_changed.connect(
            lambda k: self._save_hotkey("hotkey_ai", k)
        )
        row.addWidget(self._hotkey_ai)
        row.addStretch()
        hl.addLayout(row)

        self._hotkey_error = QLabel("")
        self._hotkey_error.setStyleSheet("color: #c62828; font-size: 11px;")
        self._hotkey_error.setVisible(False)
        hl.addWidget(self._hotkey_error)

        layout.addWidget(hotkey_frame)

        # ── AI-redigering ──
        layout.addWidget(self._section_label("AI-redigering"))
        ai_frame = self._card()
        al = QVBoxLayout(ai_frame)

        row = QHBoxLayout()
        row.addWidget(QLabel("Provider:"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItem("Lokal (Ollama)", "ollama")
        self._provider_combo.addItem("Cloud", "cloud")
        current_provider = self.config.get("ai_provider")
        for i in range(self._provider_combo.count()):
            if self._provider_combo.itemData(i) == current_provider:
                self._provider_combo.setCurrentIndex(i)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        row.addWidget(self._provider_combo)
        row.addStretch()
        al.addLayout(row)

        # Ollama model
        self._ollama_row = QHBoxLayout()
        self._ollama_row_widget = QWidget()
        ollama_inner = QHBoxLayout(self._ollama_row_widget)
        ollama_inner.setContentsMargins(0, 0, 0, 0)
        ollama_inner.addWidget(QLabel("Ollama-modell:"))
        self._ollama_model_combo = QComboBox()
        self._ollama_model_combo.setMinimumWidth(200)
        self._ollama_retry_btn = QPushButton("F\u00f6rs\u00f6k igen")
        self._load_ollama_models()
        self._ollama_model_combo.currentTextChanged.connect(
            lambda v: self._save("ollama_model", v)
        )
        ollama_inner.addWidget(self._ollama_model_combo)
        self._ollama_retry_btn.setStyleSheet(
            "QPushButton { padding: 4px 8px; font-size: 11px; }"
        )
        self._ollama_retry_btn.clicked.connect(self._load_ollama_models)
        ollama_inner.addWidget(self._ollama_retry_btn)
        ollama_inner.addStretch()
        al.addWidget(self._ollama_row_widget)

        # Cloud provider
        self._cloud_widget = QWidget()
        cloud_layout = QVBoxLayout(self._cloud_widget)
        cloud_layout.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        row.addWidget(QLabel("Cloud-provider:"))
        self._cloud_provider_combo = QComboBox()
        self._cloud_provider_combo.addItem("OpenAI", "openai")
        self._cloud_provider_combo.addItem("Anthropic", "anthropic")
        current_cp = self.config.get("cloud_provider")
        for i in range(self._cloud_provider_combo.count()):
            if self._cloud_provider_combo.itemData(i) == current_cp:
                self._cloud_provider_combo.setCurrentIndex(i)
        self._cloud_provider_combo.currentIndexChanged.connect(
            self._on_cloud_provider_changed
        )
        row.addWidget(self._cloud_provider_combo)
        row.addStretch()
        cloud_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Cloud-modell:"))
        self._cloud_model_combo = QComboBox()
        self._update_cloud_models()
        self._cloud_model_combo.currentTextChanged.connect(
            lambda v: self._save("cloud_model", v)
        )
        row.addWidget(self._cloud_model_combo)
        row.addStretch()
        cloud_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("API-nyckel:"))
        self._api_key_input = QLineEdit()
        self._api_key_input.setEchoMode(QLineEdit.Password)
        self._api_key_input.setText(self.config.get("cloud_api_key"))
        self._api_key_input.setMinimumWidth(250)
        self._api_key_input.editingFinished.connect(
            lambda: self._save("cloud_api_key", self._api_key_input.text())
        )
        row.addWidget(self._api_key_input)
        row.addStretch()
        cloud_layout.addLayout(row)

        al.addWidget(self._cloud_widget)
        self._update_provider_visibility()

        layout.addWidget(ai_frame)

        # ── Promptprofiler ──
        layout.addWidget(self._section_label("Promptprofiler"))
        prompt_frame = self._card()
        pl = QVBoxLayout(prompt_frame)

        row = QHBoxLayout()
        row.addWidget(QLabel("Aktiv profil:"))
        self._prompt_combo = QComboBox()

        self._add_profile_btn = QPushButton("Skapa ny")
        self._add_profile_btn.setStyleSheet(
            "QPushButton { padding: 4px 12px; font-size: 11px; }"
        )
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
        pl.addLayout(row)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setMaximumHeight(100)
        self._prompt_edit.setStyleSheet(
            "QTextEdit { border: 1px solid #e0e0e0; border-radius: 4px; padding: 8px; }"
        )
        self._load_prompt_text()
        pl.addWidget(self._prompt_edit)

        save_prompt_btn = QPushButton("Spara prompt")
        save_prompt_btn.setStyleSheet("""
            QPushButton { background: #e3f2fd; color: #1976D2; border: none;
                          border-radius: 6px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background: #bbdefb; }
        """)
        save_prompt_btn.clicked.connect(self._save_prompt)
        pl.addWidget(save_prompt_btn, alignment=Qt.AlignLeft)

        layout.addWidget(prompt_frame)

        # ── Mikrofon ──
        layout.addWidget(self._section_label("Mikrofon"))
        mic_frame = self._card()
        ml = QVBoxLayout(mic_frame)
        row = QHBoxLayout()
        row.addWidget(QLabel("Inspelningsenhet:"))
        self._mic_combo = QComboBox()
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
        row.addWidget(self._mic_combo)
        row.addStretch()
        ml.addLayout(row)
        layout.addWidget(mic_frame)

        # ── Ljud ──
        layout.addWidget(self._section_label("Ljud"))
        sound_frame = self._card()
        sl = QVBoxLayout(sound_frame)

        self._sound_start_cb = QCheckBox("Ljud vid inspelningsstart")
        self._sound_start_cb.setChecked(self.config.get("sound_on_record_start"))
        self._sound_start_cb.toggled.connect(
            lambda v: self._save("sound_on_record_start", v)
        )
        sl.addWidget(self._sound_start_cb)

        self._sound_done_cb = QCheckBox("Ljud vid transkribering klar")
        self._sound_done_cb.setChecked(self.config.get("sound_on_transcription_done"))
        self._sound_done_cb.toggled.connect(
            lambda v: self._save("sound_on_transcription_done", v)
        )
        sl.addWidget(self._sound_done_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Volym:"))
        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(self.config.get("sound_volume"))
        self._volume_label = QLabel(f"{self.config.get('sound_volume')}%")
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        row.addWidget(self._volume_slider)
        row.addWidget(self._volume_label)
        sl.addLayout(row)

        layout.addWidget(sound_frame)

        # ── Notiser ──
        layout.addWidget(self._section_label("Notiser"))
        notis_frame = self._card()
        nl = QVBoxLayout(notis_frame)

        self._notis_cb = QCheckBox("Visa popup vid transkribering")
        self._notis_cb.setChecked(self.config.get("show_notifications"))
        self._notis_cb.toggled.connect(
            lambda v: self._save("show_notifications", v)
        )
        nl.addWidget(self._notis_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Varaktighet:"))
        self._notis_slider = QSlider(Qt.Horizontal)
        self._notis_slider.setRange(2, 10)
        self._notis_slider.setValue(self.config.get("notification_duration_sec"))
        self._notis_label = QLabel(
            f"{self.config.get('notification_duration_sec')} sek"
        )
        self._notis_slider.valueChanged.connect(self._on_notis_duration_changed)
        row.addWidget(self._notis_slider)
        row.addWidget(self._notis_label)
        nl.addLayout(row)

        layout.addWidget(notis_frame)

        # ── \u00d6vrigt ──
        layout.addWidget(self._section_label("\u00d6vrigt"))
        other_frame = self._card()
        ol = QVBoxLayout(other_frame)

        row = QHBoxLayout()
        row.addWidget(QLabel("Max inspelningstid:"))
        self._max_rec_slider = QSlider(Qt.Horizontal)
        self._max_rec_slider.setRange(10, 120)
        self._max_rec_slider.setValue(self.config.get("max_record_sec"))
        self._max_rec_label = QLabel(f"{self.config.get('max_record_sec')} sek")
        self._max_rec_slider.valueChanged.connect(self._on_max_record_changed)
        row.addWidget(self._max_rec_slider)
        row.addWidget(self._max_rec_label)
        ol.addLayout(row)

        self._autostart_cb = QCheckBox("Autostart vid inloggning")
        self._autostart_cb.setChecked(self.config.get("autostart"))
        self._autostart_cb.toggled.connect(
            lambda v: self._save("autostart", v)
        )
        ol.addWidget(self._autostart_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Max sparad historik:"))
        self._max_history_combo = QComboBox()
        for label, val in [("100", 100), ("500", 500), ("1000", 1000), ("Obegr\u00e4nsad", 0)]:
            self._max_history_combo.addItem(label, val)
        current_max = self.config.get("max_history")
        for i in range(self._max_history_combo.count()):
            if self._max_history_combo.itemData(i) == current_max:
                self._max_history_combo.setCurrentIndex(i)
        self._max_history_combo.currentIndexChanged.connect(
            lambda i: self._save("max_history", self._max_history_combo.itemData(i))
        )
        row.addWidget(self._max_history_combo)
        row.addStretch()
        ol.addLayout(row)

        layout.addWidget(other_frame)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    # ── Helpers ──

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

    def _section_label(self, text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 11, QFont.Bold))
        label.setStyleSheet("color: #333; margin-top: 4px;")
        return label

    def _card(self):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: white; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; }"
        )
        return frame

    def _save(self, key, value):
        self.config.set(key, value)

    def _save_hotkey(self, key, value):
        other_key = "hotkey_ai" if key == "hotkey_dictate" else "hotkey_dictate"
        other_value = self.config.get(other_key)
        if value.lower() == other_value.lower():
            self._hotkey_error.setText(
                f"Konflikt: {value} anv\u00e4nds redan f\u00f6r den andra funktionen."
            )
            self._hotkey_error.setVisible(True)
            return
        self._hotkey_error.setVisible(False)
        self.config.set(key, value)

    def _on_provider_changed(self, index):
        provider = self._provider_combo.itemData(index)
        self._save("ai_provider", provider)
        self._update_provider_visibility()

    def _update_provider_visibility(self):
        is_ollama = self.config.get("ai_provider") == "ollama"
        self._ollama_row_widget.setVisible(is_ollama)
        self._cloud_widget.setVisible(not is_ollama)

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
                    self._ollama_retry_btn.setVisible(False)
                    return
        except Exception:
            pass
        self._ollama_model_combo.addItem("Ollama ej tillg\u00e4nglig \u2014 starta Ollama")
        self._ollama_model_combo.setEnabled(False)
        self._ollama_retry_btn.setVisible(True)

    def _on_cloud_provider_changed(self, index):
        provider = self._cloud_provider_combo.itemData(index)
        self._save("cloud_provider", provider)
        self._update_cloud_models()

    def _update_cloud_models(self):
        self._cloud_model_combo.clear()
        provider = self.config.get("cloud_provider")
        if provider == "openai":
            models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
        else:
            models = ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"]
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
                return

    def _save_prompt(self):
        pid = self._prompt_combo.currentData()
        text = self._prompt_edit.toPlainText().strip()
        if pid and text:
            self.config.update_prompt_profile(pid, text)

    def _add_profile(self):
        name, ok = QInputDialog.getText(
            self, "Ny promptprofil", "Namn p\u00e5 profilen:"
        )
        if ok and name.strip():
            pid = name.strip().lower().replace(" ", "-")
            self.config.add_prompt_profile(pid, name.strip(), "")
            self._update_prompt_combo()
            # Select the new one
            idx = self._prompt_combo.findData(pid)
            if idx >= 0:
                self._prompt_combo.setCurrentIndex(idx)

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
            key_name = event.text() or event.key()
            # Map Qt key codes to readable names
            from PySide6.QtCore import Qt as QtKey
            key_map = {
                QtKey.Key_F1: "F1", QtKey.Key_F2: "F2", QtKey.Key_F3: "F3",
                QtKey.Key_F4: "F4", QtKey.Key_F5: "F5", QtKey.Key_F6: "F6",
                QtKey.Key_F7: "F7", QtKey.Key_F8: "F8", QtKey.Key_F9: "F9",
                QtKey.Key_F10: "F10", QtKey.Key_F11: "F11", QtKey.Key_F12: "F12",
                QtKey.Key_Escape: "Escape", QtKey.Key_Space: "Space",
                QtKey.Key_Return: "Return", QtKey.Key_Tab: "Tab",
            }
            key_code = event.key()
            if key_code in key_map:
                key_str = key_map[key_code]
            elif event.text():
                key_str = event.text().upper()
            else:
                key_str = f"Key_{key_code}"

            self._capturing = False
            self.setText(key_str)
            self.setStyleSheet("""
                QPushButton { background: white; border: 1px solid #e0e0e0;
                              border-radius: 4px; padding: 6px 12px; }
            """)
            self.key_changed.emit(key_str)
        else:
            super().keyPressEvent(event)
