"""WhisperTyper Desktop — main entry point."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QThread, Slot

from config import ConfigManager
from engine import WhisperEngine
from ui.dashboard import Dashboard

ASSETS = Path(__file__).parent / "assets"


class ModelLoaderThread(QThread):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        self.engine.load_model()


class WhisperTyperApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setApplicationName("WhisperTyper")

        self.config = ConfigManager()
        self.engine = WhisperEngine(self.config)

        # Dashboard
        self.dashboard = Dashboard(self.config, self.engine)

        # System tray
        self._setup_tray()

        # Connect engine signals to tray
        self.engine.model_loading.connect(self._on_model_loading)
        self.engine.model_ready.connect(self._on_model_ready)
        self.engine.recording_started.connect(self._on_recording)
        self.engine.transcription_started.connect(self._on_transcribing)
        self.engine.transcription_done.connect(self._on_transcription_done)
        self.engine.ai_started.connect(self._on_ai)
        self.engine.ai_done.connect(self._on_ai_done)

        # Load model in background
        self._loader = ModelLoaderThread(self.engine)
        self._loader.finished.connect(self._on_model_loaded)
        self._loader.start()

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self.app)
        icon_path = ASSETS / "icon_loading.png"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        self.tray.setToolTip("WhisperTyper \u2014 Laddar...")
        self.tray.activated.connect(self._on_tray_activated)

        # Context menu
        menu = QMenu()

        self._last_text_action = QAction("(ingen transkribering)", menu)
        self._last_text_action.triggered.connect(self._copy_last_text)
        menu.addAction(self._last_text_action)

        menu.addSeparator()

        self._profile_menu = menu.addMenu("Promptprofil")
        self._update_profile_menu()

        menu.addSeparator()

        open_action = QAction("\u00d6ppna dashboard", menu)
        open_action.triggered.connect(self._show_dashboard)
        menu.addAction(open_action)

        settings_action = QAction("Inst\u00e4llningar", menu)
        settings_action.triggered.connect(self.dashboard.show_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        quit_action = QAction("Avsluta", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()

    def _update_profile_menu(self):
        self._profile_menu.clear()
        active = self.config.get("active_prompt_profile")
        for p in self.config.get_prompt_profiles():
            action = QAction(p["name"], self._profile_menu)
            action.setCheckable(True)
            action.setChecked(p["id"] == active)
            pid = p["id"]
            action.triggered.connect(
                lambda checked, pid=pid: self._set_profile(pid)
            )
            self._profile_menu.addAction(action)

    def _set_profile(self, profile_id):
        self.config.set("active_prompt_profile", profile_id)
        self._update_profile_menu()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:  # Left click
            if self.dashboard.isVisible():
                self.dashboard.hide()
            else:
                self._show_dashboard()

    def _show_dashboard(self):
        self.dashboard.show()
        self.dashboard.raise_()
        self.dashboard.activateWindow()

    def _copy_last_text(self):
        text = self.engine.last_typed_text
        if text:
            import pyperclip
            pyperclip.copy(text)

    def _set_tray_icon(self, name):
        icon_path = ASSETS / f"{name}.png"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))

    @Slot()
    def _on_model_loading(self):
        self._set_tray_icon("icon_loading")
        self.tray.setToolTip("WhisperTyper \u2014 Laddar modell...")

    @Slot()
    def _on_model_ready(self):
        self._set_tray_icon("icon_ready")
        self.tray.setToolTip("WhisperTyper \u2014 Redo")
        if self.config.get("show_notifications"):
            self.tray.showMessage(
                "WhisperTyper",
                "Redo att diktera!",
                QSystemTrayIcon.Information,
                3000,
            )

    def _on_model_loaded(self):
        self.engine.start_hotkey_listener()

    @Slot(str)
    def _on_recording(self, mode):
        self._set_tray_icon("icon_recording")
        self.tray.setToolTip("WhisperTyper \u2014 Spelar in...")

    @Slot()
    def _on_transcribing(self):
        self._set_tray_icon("icon_transcribing")
        self.tray.setToolTip("WhisperTyper \u2014 Transkriberar...")

    @Slot(str, str)
    def _on_transcription_done(self, text, mode):
        self._set_tray_icon("icon_ready")
        self.tray.setToolTip("WhisperTyper \u2014 Redo")
        truncated = text[:80] + "..." if len(text) > 80 else text
        self._last_text_action.setText(truncated)
        if self.config.get("show_notifications") and mode == "dictate":
            duration = self.config.get("notification_duration_sec") * 1000
            self.tray.showMessage(
                "WhisperTyper", text, QSystemTrayIcon.Information, duration
            )

    @Slot()
    def _on_ai(self):
        self._set_tray_icon("icon_ai")
        self.tray.setToolTip("WhisperTyper \u2014 AI bearbetar...")

    @Slot(str, str)
    def _on_ai_done(self, original, edited):
        self._set_tray_icon("icon_ready")
        self.tray.setToolTip("WhisperTyper \u2014 Redo")
        truncated = edited[:80] + "..." if len(edited) > 80 else edited
        self._last_text_action.setText(truncated)

    def _quit(self):
        self.engine.cleanup()
        self.tray.hide()
        self.app.quit()

    def run(self):
        return self.app.exec()


def main():
    app = WhisperTyperApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
