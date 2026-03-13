from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QFont

from ui.tab_live import LiveTab
from ui.tab_history import HistoryTab
from ui.tab_settings import SettingsTab


class Dashboard(QMainWindow):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self.setWindowTitle("WhisperTyper")
        self.setMinimumSize(500, 400)
        self.resize(550, 500)

        self.setStyleSheet("""
            QMainWindow { background: #f8f9fa; }
            QTabWidget::pane { border: none; background: #f8f9fa; }
            QTabBar::tab {
                background: #f0f0f0; border: none; padding: 10px 24px;
                font-size: 13px; color: #666;
            }
            QTabBar::tab:selected {
                background: #f8f9fa; color: #1976D2; font-weight: bold;
                border-bottom: 2px solid #1976D2;
            }
        """)

        self._tabs = QTabWidget()
        self._live_tab = LiveTab(config, engine)
        self._history_tab = HistoryTab(config, engine)
        self._settings_tab = SettingsTab(config, engine)

        self._tabs.addTab(self._live_tab, "Live")
        self._tabs.addTab(self._history_tab, "Historik")
        self._tabs.addTab(self._settings_tab, "Inst\u00e4llningar")

        self._settings_tab.profiles_changed.connect(self._live_tab.refresh_profiles)
        self._settings_tab.hotkey_changed.connect(
            lambda: self.engine.restart_hotkey_listener()
        )

        self.setCentralWidget(self._tabs)

    def show_settings(self):
        self._tabs.setCurrentWidget(self._settings_tab)
        self.show()
        self.raise_()
        self.activateWindow()

    @property
    def profiles_changed(self):
        return self._settings_tab.profiles_changed

    @property
    def hotkey_changed(self):
        return self._settings_tab.hotkey_changed

    def closeEvent(self, event):
        event.ignore()
        self.hide()
