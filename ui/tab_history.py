from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QDialog, QTextEdit, QDialogButtonBox,
)
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
import threading


class HistoryTab(QWidget):
    def __init__(self, config, engine):
        super().__init__()
        self.config = config
        self.engine = engine
        self._setup_ui()
        self._connect_signals()
        self._load_history()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Search bar
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("S\u00f6k i historik...")
        self._search_input.setStyleSheet("""
            QLineEdit { background: white; border: 1px solid #e0e0e0;
                        border-radius: 6px; padding: 8px 12px; font-size: 13px; }
        """)
        self._search_input.textChanged.connect(self._filter_history)
        search_layout.addWidget(self._search_input)

        self._clear_btn = QPushButton("Rensa historik")
        self._clear_btn.setStyleSheet("""
            QPushButton { background: #ffebee; color: #c62828; border: none;
                          border-radius: 6px; padding: 8px 16px; font-size: 12px; }
            QPushButton:hover { background: #ffcdd2; }
        """)
        self._clear_btn.clicked.connect(self._clear_history)
        search_layout.addWidget(self._clear_btn)

        layout.addLayout(search_layout)

        # History list
        self._list = QListWidget()
        self._list.setStyleSheet("""
            QListWidget { background: white; border: 1px solid #e0e0e0;
                          border-radius: 8px; font-size: 13px; }
            QListWidget::item { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background: #e3f2fd; }
        """)
        self._list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._list)

    def _connect_signals(self):
        self.engine.transcription_done.connect(self._on_new_transcription)
        self.engine.ai_done.connect(self._on_ai_done)

    def _load_history(self):
        self._list.clear()
        for entry in self.config.get_history():
            self._add_item(entry)

    def _add_item(self, entry):
        text = entry["text"]
        truncated = text[:100] + "..." if len(text) > 100 else text
        timestamp = entry.get("timestamp", "")[:16].replace("T", " ")
        ai_marker = " [AI]" if entry.get("ai_edited") else ""
        display = f"{truncated}\n{timestamp}{ai_marker}"

        item = QListWidgetItem(display)
        item.setData(Qt.UserRole, entry)
        self._list.addItem(item)

    @Slot(str, str)
    def _on_new_transcription(self, text, mode):
        if mode == "dictate":
            self._load_history()

    @Slot(str, str)
    def _on_ai_done(self, original, edited):
        self._load_history()

    def _filter_history(self, query):
        for i in range(self._list.count()):
            item = self._list.item(i)
            entry = item.data(Qt.UserRole)
            visible = query.lower() in entry["text"].lower() if query else True
            item.setHidden(not visible)

    def _show_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if not item:
            return
        entry = item.data(Qt.UserRole)

        menu = QMenu(self)
        copy_action = QAction("Kopiera", self)
        copy_action.triggered.connect(lambda: self._copy_entry(entry))
        menu.addAction(copy_action)

        ai_action = QAction("Redigera med AI", self)
        ai_action.triggered.connect(lambda: self._ai_edit_entry(entry))
        menu.addAction(ai_action)

        menu.addSeparator()
        delete_action = QAction("Ta bort", self)
        delete_action.triggered.connect(lambda: self._delete_entry(entry))
        menu.addAction(delete_action)

        menu.exec(self._list.mapToGlobal(pos))

    def _copy_entry(self, entry):
        import pyperclip
        pyperclip.copy(entry["text"])

    def _ai_edit_entry(self, entry):
        dialog = QDialog(self)
        dialog.setWindowTitle("Redigera med AI")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)

        text_preview = entry["text"][:200]
        layout.addWidget(QLabel(f"Ursprunglig text: {text_preview}"))

        instruction_input = QTextEdit()
        instruction_input.setPlaceholderText("Skriv instruktion...")
        instruction_input.setMaximumHeight(80)
        layout.addWidget(instruction_input)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            instruction = instruction_input.toPlainText().strip()
            if instruction:
                threading.Thread(
                    target=self.engine.ai_edit_text,
                    args=(instruction, entry["text"]),
                    daemon=True,
                ).start()

    def _delete_entry(self, entry):
        self.config.delete_history_entry(entry["id"])
        self._load_history()

    def _clear_history(self):
        reply = QMessageBox.question(
            self,
            "Rensa historik",
            "\u00c4r du s\u00e4ker? Detta g\u00e5r inte att \u00e5ngra.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.config.clear_history()
            self._load_history()
