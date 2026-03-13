# F10 AI-Edit Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix unreliable AI editing (F10) by adding minimum recording duration, separated text state, window tracking, Ctrl+V stability, and Ctrl+F9 as default hotkey.

**Architecture:** Replace single `last_typed_text` with three fields (`last_dictated_text`, `last_injected_text`, `last_injected_window`). Add `win32gui` for window tracking with cross-platform fallback. Rewrite hotkey listener to support modifier+key combos. Add minimum recording duration guard.

**Tech Stack:** PySide6, pynput, pywin32 (Windows-only, optional), pyaudio

**Spec:** `docs/superpowers/specs/2026-03-13-f10-ai-edit-redesign.md`

---

## Chunk 1: Foundation changes

### Task 1: Config default + requirements

**Files:**
- Modify: `config.py:16`
- Modify: `requirements.txt`
- Modify: `tests/test_config.py:21`

- [ ] **Step 1: Update test for new default hotkey**

In `tests/test_config.py`, update the existing test and add a new one:

```python
# In test_default_config_created_on_first_load, change line 21:
assert cm.get("hotkey_ai") == "ctrl+f9"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_config.py::TestConfigManager::test_default_config_created_on_first_load -v`
Expected: FAIL — `"F10" != "ctrl+f9"`

- [ ] **Step 3: Update config.py default**

In `config.py` line 16, change:
```python
"hotkey_ai": "ctrl+f9",
```

- [ ] **Step 4: Update requirements.txt**

Add at end of `requirements.txt`:
```
pywin32; sys_platform == "win32"  # Window tracking (optional)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add config.py requirements.txt tests/test_config.py
git commit -m "feat: change default AI hotkey to ctrl+f9, add pywin32 dep"
```

---

### Task 2: Minimum recording duration

**Files:**
- Modify: `engine.py:35-53,139-141,175,192-198`
- Modify: `ui/tab_live.py:1-8,193-196`

- [ ] **Step 1: Add `_last_recording_duration` to engine `__init__`**

In `engine.py`, after line 46 (`self._recording_done = threading.Event()`), add:
```python
        self._last_recording_duration = 0.0
```

- [ ] **Step 2: Save duration in `_record_audio`**

In `engine.py`, after line 175 (`duration = time.time() - start`), add:
```python
        self._last_recording_duration = duration
```

- [ ] **Step 3: Add duration check in `_process_recording`**

In `engine.py`, replace lines 192-198 (`def _process_recording` start):
```python
    def _process_recording(self, mode):
        if self._last_recording_duration < 0.5:
            self.error.emit("Inspelning för kort")
            return

        with self._audio_lock:
            frames = list(self._audio_frames)

        if not frames:
            self.error.emit("Inget ljud inspelat.")
            return
```

- [ ] **Step 4: Update Live tab `_on_error` to show temporary message**

In `ui/tab_live.py`, add `QTimer` to imports (line 5):
```python
from PySide6.QtCore import Qt, Slot, QTimer
```

Replace `_on_error` method (lines 193-196):
```python
    @Slot(str)
    def _on_error(self, msg):
        self._status_dot.setStyleSheet("color: #FF9800; font-size: 20px;")
        self._status_text.setText(msg)
        QTimer.singleShot(2000, self._reset_status)

    def _reset_status(self):
        self._status_dot.setStyleSheet("color: #4CAF50; font-size: 20px;")
        self._status_text.setText("Redo")
```

- [ ] **Step 5: Commit**

```bash
git add engine.py ui/tab_live.py
git commit -m "feat: add minimum recording duration guard (0.5s)"
```

---

### Task 3: Ctrl+V stability fix

**Files:**
- Modify: `engine.py:358-367`

- [ ] **Step 1: Fix `_type_text` timing**

In `engine.py`, replace lines 358-367 (the try block inside `_type_text`):
```python
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            with self._kb_controller.pressed(pynput_keyboard.Key.ctrl):
                time.sleep(0.05)
                self._kb_controller.tap("v")
            time.sleep(0.2)
            pyperclip.copy(old_clipboard)
            self.last_typed_text = text
        except Exception as e:
            self.error.emit(f"Kunde inte skriva in text: {e}")
```

Note: `self.last_typed_text = text` will be replaced in Task 4. Keep it for now so existing code still works.

- [ ] **Step 2: Commit**

```bash
git add engine.py
git commit -m "fix: improve Ctrl+V reliability with timing adjustments"
```

---

## Chunk 2: Text state + window tracking

### Task 4: Replace `last_typed_text` with three fields + window tracking

This is the core change. All `last_typed_text` references are replaced in one task to avoid broken intermediate states.

**Files:**
- Modify: `engine.py:35-53,192-267,271-348,350-374,394-412`
- Modify: `main.py:125-129`

- [ ] **Step 1: Add `_get_foreground_window` helper to engine**

In `engine.py`, add after the `_get_mic_index` method (after line 190):
```python
    def _get_foreground_window(self):
        """Return active window HWND, or 0 if win32gui unavailable."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            return hwnd if hwnd else 0
        except ImportError:
            return 0
```

- [ ] **Step 2: Replace `__init__` text state fields**

In `engine.py`, replace lines 48-50:
```python
        # Text injection tracking
        self.last_typed_text = ""
        self._kb_controller = pynput_keyboard.Controller()
```
with:
```python
        # Text injection tracking
        self.last_dictated_text = ""
        self.last_injected_text = ""
        self.last_injected_window = 0
        self._kb_controller = pynput_keyboard.Controller()
```

- [ ] **Step 3: Add `last_dictated_text` assignment in F9 flow**

In `engine.py`, in `_process_recording`, after the `self._type_text(text)` call in the dictate branch (line 236), add:
```python
            self.last_dictated_text = text
```

So lines 234-239 become:
```python
        if mode == "dictate":
            text = smart_punctuation(text)
            self._type_text(text)
            self.last_dictated_text = text
            self._play_sound("done")
            self.transcription_done.emit(text, mode)
            self.config.add_history_entry(text, 0, mode)
```

- [ ] **Step 4: Update `_handle_ai_edit`**

Replace the entire `_handle_ai_edit` method (lines 244-266):
```python
    def _handle_ai_edit(self, instruction):
        if not self.last_dictated_text:
            self.error.emit("Ingen tidigare text att redigera. Diktera med F9 först.")
            return

        self.ai_started.emit()
        provider = self.config.get("ai_provider")

        try:
            if provider == "ollama":
                new_text = self._ai_ollama(instruction)
            else:
                new_text = self._ai_cloud(instruction)

            if new_text:
                self._replace_last_text(new_text)
                self.ai_done.emit(self.last_dictated_text, new_text)
                self.config.add_history_entry(
                    new_text, 0, "ai_edit",
                    original_text=self.last_dictated_text,
                )
        except Exception as e:
            self.error.emit(f"AI-fel: {e}")
```

- [ ] **Step 5: Update `_ai_ollama` to use `last_dictated_text`**

In `engine.py`, in `_ai_ollama` (line 283), change:
```python
                        "content": f'Ursprunglig text: "{self.last_typed_text}"\n\nInstruktion: {instruction}',
```
to:
```python
                        "content": f'Ursprunglig text: "{self.last_dictated_text}"\n\nInstruktion: {instruction}',
```

- [ ] **Step 6: Update `_ai_cloud` to use `last_dictated_text`**

In `engine.py`, in `_ai_cloud`, change both references to `self.last_typed_text` (lines 304 and 340) to `self.last_dictated_text`.

Line 304:
```python
                "content": f'Ursprunglig text: "{self.last_dictated_text}"\n\nInstruktion: {instruction}',
```

Line 340:
```python
                            "content": f'Ursprunglig text: "{self.last_dictated_text}"\n\nInstruktion: {instruction}',
```

- [ ] **Step 7: Update `_type_text` with window tracking**

Replace the entire `_type_text` method (lines 350-367):
```python
    def _type_text(self, text):
        if not text:
            return
        self.last_injected_window = self._get_foreground_window()
        old_clipboard = ""
        try:
            old_clipboard = pyperclip.paste()
        except Exception:
            pass
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            with self._kb_controller.pressed(pynput_keyboard.Key.ctrl):
                time.sleep(0.05)
                self._kb_controller.tap("v")
            time.sleep(0.2)
            pyperclip.copy(old_clipboard)
            self.last_injected_text = text
        except Exception as e:
            self.error.emit(f"Kunde inte skriva in text: {e}")
```

- [ ] **Step 8: Update `_replace_last_text` with window comparison + backspace throttling**

Replace the entire `_replace_last_text` method (lines 369-374):
```python
    def _replace_last_text(self, new_text):
        current_window = self._get_foreground_window()
        same_window = (
            current_window != 0
            and self.last_injected_window != 0
            and current_window == self.last_injected_window
        )
        if same_window and self.last_injected_text:
            for i in range(len(self.last_injected_text)):
                self._kb_controller.tap(pynput_keyboard.Key.backspace)
                if i % 20 == 19:
                    time.sleep(0.01)
            time.sleep(0.05)
        self._type_text(new_text)
```

- [ ] **Step 9: Update `ai_edit_text` (UI-triggered path)**

Replace the `ai_edit_text` method (lines 394-412):
```python
    def ai_edit_text(self, instruction, original_text):
        """AI edit triggered from UI (not via hotkey)."""
        self.ai_started.emit()
        try:
            provider = self.config.get("ai_provider")
            # Temporarily use original_text for the AI prompt
            saved = self.last_dictated_text
            self.last_dictated_text = original_text
            try:
                if provider == "ollama":
                    new_text = self._ai_ollama(instruction)
                else:
                    new_text = self._ai_cloud(instruction)
            finally:
                self.last_dictated_text = saved
            if new_text:
                self.ai_done.emit(original_text, new_text)
                self.config.add_history_entry(
                    new_text, 0, "ai_edit", original_text=original_text
                )
                return new_text
        except Exception as e:
            self.error.emit(f"AI-fel: {e}")
        return None
```

- [ ] **Step 10: Update `main.py` reference**

In `main.py`, line 126, change:
```python
        text = self.engine.last_typed_text
```
to:
```python
        text = self.engine.last_injected_text
```

- [ ] **Step 11: Commit**

```bash
git add engine.py main.py
git commit -m "feat: separate text state with window tracking for reliable AI edit"
```

---

## Chunk 3: Hotkey combo support

### Task 5: Rewrite hotkey listener for modifier+key combos

**Files:**
- Modify: `engine.py:35-53,78-118`

- [ ] **Step 1: Add `_active_modifiers` and `_active_hotkey` to `__init__`**

In `engine.py`, after the hotkey listener line (line 53 `self._hotkey_listener = None`), add:
```python
        self._active_modifiers = set()
        self._active_hotkey = None
```

- [ ] **Step 2: Rewrite `_parse_key` for combo support**

Replace `_parse_key` method (lines 108-110):
```python
    def _parse_key(self, key_str):
        """Parse 'ctrl+f9' → {'modifiers': {'ctrl'}, 'key': 'f9'}"""
        parts = key_str.lower().split("+")
        modifiers = set()
        key = parts[-1]
        for p in parts[:-1]:
            if p in ("ctrl", "alt", "shift"):
                modifiers.add(p)
        return {"modifiers": modifiers, "key": key}
```

- [ ] **Step 3: Rewrite `start_hotkey_listener` with modifier tracking**

Replace the entire `start_hotkey_listener` method (lines 78-102):
```python
    def start_hotkey_listener(self):
        """Start global hotkey listener."""
        dictate_parsed = self._parse_key(self.config.get("hotkey_dictate"))
        ai_parsed = self._parse_key(self.config.get("hotkey_ai"))

        def on_press(key):
            # Track modifiers
            if key in (pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
                self._active_modifiers.add("ctrl")
            elif key in (pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r, pynput_keyboard.Key.alt_gr):
                self._active_modifiers.add("alt")
            elif key in (pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
                self._active_modifiers.add("shift")

            if self.model is None or self._is_recording:
                return

            normalized = self._normalize_key(key)
            for hotkey_config, mode in [(dictate_parsed, "dictate"), (ai_parsed, "ai")]:
                if normalized == hotkey_config["key"] and self._active_modifiers == hotkey_config["modifiers"]:
                    self._start_recording(mode)
                    self._active_hotkey = hotkey_config["key"]
                    break

        def on_release(key):
            # Track modifiers
            if key in (pynput_keyboard.Key.ctrl_l, pynput_keyboard.Key.ctrl_r):
                self._active_modifiers.discard("ctrl")
            elif key in (pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r, pynput_keyboard.Key.alt_gr):
                self._active_modifiers.discard("alt")
            elif key in (pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r):
                self._active_modifiers.discard("shift")

            normalized = self._normalize_key(key)
            if normalized == self._active_hotkey and self._is_recording:
                self._stop_recording()
                self._active_hotkey = None

        self._hotkey_listener = pynput_keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
        )
        self._hotkey_listener.daemon = True
        self._hotkey_listener.start()
```

- [ ] **Step 4: Add `restart_hotkey_listener`**

After `stop_hotkey_listener` (line 106), add:
```python
    def restart_hotkey_listener(self):
        """Restart listener to pick up new hotkey config."""
        self.stop_hotkey_listener()
        self._active_modifiers.clear()
        self._active_hotkey = None
        self.start_hotkey_listener()
```

- [ ] **Step 5: Commit**

```bash
git add engine.py
git commit -m "feat: hotkey listener with modifier+key combo support"
```

---

### Task 6: Add `_parse_key` tests

**Files:**
- Create: `tests/test_engine.py`

- [ ] **Step 1: Write tests for `_parse_key`**

Create `tests/test_engine.py`:
```python
import pytest
from unittest.mock import MagicMock


class TestParseKey:
    def _make_engine(self):
        """Create engine with mocked config (avoids loading Whisper)."""
        from engine import WhisperEngine
        from unittest.mock import patch

        mock_config = MagicMock()
        mock_config.get.return_value = "medium"

        with patch.object(WhisperEngine, '__init__', lambda self, config: None):
            engine = WhisperEngine.__new__(WhisperEngine)
        # Manually set what _parse_key needs (nothing beyond self)
        return engine

    def test_simple_key(self):
        engine = self._make_engine()
        result = engine._parse_key("F9")
        assert result == {"modifiers": set(), "key": "f9"}

    def test_ctrl_combo(self):
        engine = self._make_engine()
        result = engine._parse_key("ctrl+f9")
        assert result == {"modifiers": {"ctrl"}, "key": "f9"}

    def test_ctrl_combo_case_insensitive(self):
        engine = self._make_engine()
        result = engine._parse_key("Ctrl+F9")
        assert result == {"modifiers": {"ctrl"}, "key": "f9"}

    def test_multi_modifier(self):
        engine = self._make_engine()
        result = engine._parse_key("ctrl+shift+a")
        assert result == {"modifiers": {"ctrl", "shift"}, "key": "a"}

    def test_single_letter(self):
        engine = self._make_engine()
        result = engine._parse_key("A")
        assert result == {"modifiers": set(), "key": "a"}
```

- [ ] **Step 2: Run tests**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/test_engine.py -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_engine.py
git commit -m "test: add _parse_key unit tests for hotkey combo parsing"
```

---

### Task 7: KeyCaptureButton with modifier support + hotkey_changed signal

**Files:**
- Modify: `ui/tab_settings.py:11-13,426-436,572-626`
- Modify: `ui/dashboard.py:40-52`
- Modify: `main.py:49-50`

- [ ] **Step 1: Add `hotkey_changed` signal to SettingsTab**

In `ui/tab_settings.py`, line 13 (after `profiles_changed = Signal()`), add:
```python
    hotkey_changed = Signal()
```

- [ ] **Step 2: Emit `hotkey_changed` in `_save_hotkey`**

In `ui/tab_settings.py`, at end of `_save_hotkey` (after line 436 `self.config.set(key, value)`), add:
```python
        self.hotkey_changed.emit()
```

- [ ] **Step 3: Rewrite `KeyCaptureButton.keyPressEvent` for modifier combos**

Replace the `keyPressEvent` method (lines 597-626):
```python
    def keyPressEvent(self, event):
        if self._capturing:
            from PySide6.QtCore import Qt as QtKey
            key_code = event.key()

            # Ignore lone modifier presses
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

            # Build modifier prefix
            parts = []
            mods = event.modifiers()
            if mods & QtKey.ControlModifier:
                parts.append("Ctrl")
            if mods & QtKey.AltModifier:
                parts.append("Alt")
            if mods & QtKey.ShiftModifier:
                parts.append("Shift")

            # Key name
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
```

- [ ] **Step 4: Wire `hotkey_changed` in Dashboard**

In `ui/dashboard.py`, after line 40 (`self._settings_tab.profiles_changed.connect(...)`), add:
```python
        self._settings_tab.hotkey_changed.connect(
            lambda: self.engine.restart_hotkey_listener()
        )
```

Add `hotkey_changed` property after `profiles_changed` property (after line 52):
```python
    @property
    def hotkey_changed(self):
        return self._settings_tab.hotkey_changed
```

- [ ] **Step 5: Commit**

```bash
git add ui/tab_settings.py ui/dashboard.py
git commit -m "feat: KeyCaptureButton with modifier combos + hotkey restart on change"
```

---

### Task 8: Final integration test

- [ ] **Step 1: Run all tests**

Run: `cd /home/rober/Projects/Whisper && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Verify no remaining `last_typed_text` references**

Run: `cd /home/rober/Projects/Whisper && grep -rn "last_typed_text" --include="*.py" .`
Expected: No matches (zero output)

- [ ] **Step 3: Push to git for Windows testing**

```bash
git push
```
