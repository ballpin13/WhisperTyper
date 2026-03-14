from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame,
)
from PySide6.QtCore import Qt, Slot, QTimer
from ui.tab_settings import NoScrollComboBox
from datetime import datetime
import threading


class LiveTab(QWidget):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setStyleSheet("LiveTab { background: white; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(4)

        # Status row (no card)
        status_row = QHBoxLayout()
        self._status_dot = QLabel("\u25cf")
        self._status_dot.setStyleSheet("color: #9E9E9E; font-size: 18px;")
        self._status_text = QLabel("Laddar modell...")
        self._status_text.setStyleSheet("font-size: 14px; font-weight: 500; color: #333;")
        status_row.addWidget(self._status_dot)
        status_row.addWidget(self._status_text)
        status_row.addStretch()

        # Profile combo in status row
        profile_label = QLabel("PROFIL")
        profile_label.setStyleSheet(
            "color: #1976D2; font-size: 10px; font-weight: bold;"
        )
        self._profile_combo = NoScrollComboBox()
        self._profile_combo.setMinimumWidth(150)
        self._update_profile_combo()
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        status_row.addWidget(profile_label)
        status_row.addWidget(self._profile_combo)

        layout.addLayout(status_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #eee; border: none;")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        layout.addSpacing(8)

        # Transcription section (no card)
        trans_header = QLabel("SENASTE TRANSKRIBERING")
        trans_header.setStyleSheet(
            "color: #1976D2; font-size: 10px; font-weight: bold; margin-top: 4px;"
        )
        layout.addWidget(trans_header)

        self._trans_text = QLabel("Ingen transkribering \u00e4nnu.")
        self._trans_text.setWordWrap(True)
        self._trans_text.setStyleSheet("font-size: 14px; color: #333; line-height: 1.5;")
        self._trans_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._trans_text)

        self._trans_meta = QLabel("")
        self._trans_meta.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._trans_meta)

        # Buttons
        btn_layout = QHBoxLayout()
        self._copy_btn = QPushButton("Kopiera")
        self._copy_btn.setStyleSheet("""
            QPushButton { background: #e3f2fd; color: #1976D2; border: none;
                          border-radius: 6px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background: #bbdefb; }
        """)
        self._copy_btn.clicked.connect(self._copy_text)

        self._ai_btn = QPushButton("Redigera med AI")
        self._ai_btn.setStyleSheet("""
            QPushButton { background: #e8f5e9; color: #388E3C; border: none;
                          border-radius: 6px; padding: 6px 16px; font-size: 12px; }
            QPushButton:hover { background: #c8e6c9; }
        """)
        self._ai_btn.clicked.connect(self._toggle_ai_edit)

        btn_layout.addWidget(self._copy_btn)
        btn_layout.addWidget(self._ai_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # AI edit area (hidden by default)
        self._ai_frame = QFrame()
        self._ai_frame.setVisible(False)
        ai_layout = QHBoxLayout(self._ai_frame)
        ai_layout.setContentsMargins(0, 8, 0, 0)
        self._ai_input = QTextEdit()
        self._ai_input.setPlaceholderText(
            "Skriv en instruktion, t.ex. 'g\u00f6r texten mer formell'..."
        )
        self._ai_input.setMaximumHeight(60)
        self._ai_send_btn = QPushButton("Skicka")
        self._ai_send_btn.setStyleSheet("""
            QPushButton { background: #388E3C; color: white; border: none;
                          border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background: #2E7D32; }
        """)
        self._ai_send_btn.clicked.connect(self._send_ai_edit)
        ai_layout.addWidget(self._ai_input)
        ai_layout.addWidget(self._ai_send_btn, alignment=Qt.AlignTop)
        layout.addWidget(self._ai_frame)

        layout.addStretch()

    def _connect_signals(self):
        self.engine.model_loading.connect(self._on_model_loading)
        self.engine.model_ready.connect(self._on_model_ready)
        self.engine.recording_started.connect(self._on_recording_started)
        self.engine.transcription_started.connect(self._on_transcription_started)
        self.engine.transcription_done.connect(self._on_transcription_done)
        self.engine.ai_started.connect(self._on_ai_started)
        self.engine.ai_done.connect(self._on_ai_done)
        self.engine.error.connect(self._on_error)

    def _update_profile_combo(self):
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        active = self.config.get("active_prompt_profile")
        for i, p in enumerate(self.config.get_prompt_profiles()):
            self._profile_combo.addItem(p["name"], p["id"])
            if p["id"] == active:
                self._profile_combo.setCurrentIndex(i)
        self._profile_combo.blockSignals(False)

    def refresh_profiles(self):
        """Called when profiles change in settings."""
        self._update_profile_combo()

    def _on_profile_changed(self, index):
        profile_id = self._profile_combo.currentData()
        if profile_id:
            self.config.set("active_prompt_profile", profile_id)

    @Slot()
    def _on_model_loading(self):
        self._status_dot.setStyleSheet("color: #9E9E9E; font-size: 18px;")
        self._status_text.setText("Laddar modell...")

    @Slot()
    def _on_model_ready(self):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 18px;")
        self._status_text.setText("Redo")

    @Slot(str)
    def _on_recording_started(self, mode):
        self._status_dot.setStyleSheet("color: #f44336; font-size: 18px;")
        mode_text = "Spelar in..." if mode == "dictate" else "Spelar in AI-instruktion..."
        self._status_text.setText(mode_text)

    @Slot()
    def _on_transcription_started(self):
        self._status_dot.setStyleSheet("color: #FFC107; font-size: 18px;")
        self._status_text.setText("Transkriberar...")

    @Slot(str, str)
    def _on_transcription_done(self, text, mode):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 18px;")
        self._status_text.setText("Redo")
        if mode == "dictate":
            self._trans_text.setText(text)
            self._trans_meta.setText(
                f"{datetime.now().strftime('%H:%M')} \u2022 F9 diktering"
            )

    @Slot()
    def _on_ai_started(self):
        self._status_dot.setStyleSheet("color: #2196F3; font-size: 18px;")
        self._status_text.setText("AI bearbetar...")

    @Slot(str, str)
    def _on_ai_done(self, original, edited):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 18px;")
        self._status_text.setText("Redo")
        self._trans_text.setText(edited)
        self._trans_meta.setText(
            f"{datetime.now().strftime('%H:%M')} \u2022 AI-redigerad"
        )

    @Slot(str)
    def _on_error(self, msg):
        self._status_dot.setStyleSheet("color: #FF9800; font-size: 18px;")
        self._status_text.setText(msg)
        QTimer.singleShot(2000, self._reset_status)

    def _reset_status(self):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 18px;")
        self._status_text.setText("Redo")

    def _copy_text(self):
        text = self._trans_text.text()
        if text and text != "Ingen transkribering \u00e4nnu.":
            import pyperclip
            pyperclip.copy(text)

    def _toggle_ai_edit(self):
        self._ai_frame.setVisible(not self._ai_frame.isVisible())

    def _send_ai_edit(self):
        instruction = self._ai_input.toPlainText().strip()
        if not instruction:
            return
        original = self._trans_text.text()
        if not original or original == "Ingen transkribering \u00e4nnu.":
            return
        self._ai_input.clear()
        self._ai_frame.setVisible(False)
        threading.Thread(
            target=self.engine.ai_edit_text,
            args=(instruction, original),
            daemon=True,
        ).start()
