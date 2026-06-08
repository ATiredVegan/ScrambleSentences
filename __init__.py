"""
ScrambleSentences for language learning — Anki Add-on
Reads the Word field, generates example sentences via Claude AI,
and writes them all into the Front field. A JS snippet in the card
template picks one at random to display during review.
Clicking Generate shows a small dialog to pick the language first.
"""

import json
import re
import urllib.request
import urllib.error
from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.utils import showWarning, tooltip

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_WORD_FIELD  = "Word"
DEFAULT_FRONT_FIELD = "Front"

LANGUAGES = [
    "English", "Spanish", "French", "German", "Italian",
    "Portuguese", "Japanese", "Chinese", "Korean", "Arabic",
    "Russian", "Dutch", "Polish", "Turkish", "Swedish",
]

# ── Config ────────────────────────────────────────────────────────────────────

def get_config():
    cfg = mw.addonManager.getConfig(__name__) or {}
    return {
        "api_key":             cfg.get("api_key", ""),
        "model":               cfg.get("model", "claude-sonnet-4-5"),
        "word_field":          cfg.get("word_field", DEFAULT_WORD_FIELD),
        "front_field":         cfg.get("front_field", DEFAULT_FRONT_FIELD),
        "num_sentences":       cfg.get("num_sentences", 3),
        "default_language":    cfg.get("default_language", "English"),
        "difficulty":          cfg.get("difficulty", "intermediate"),
        "include_translation": cfg.get("include_translation", False),
        "extra_languages":     cfg.get("extra_languages", []),
    }

def save_config(updates: dict):
    cfg = get_config()
    cfg.update(updates)
    mw.addonManager.writeConfig(__name__, cfg)

def get_language_list():
    cfg = get_config()
    extras = [l.strip() for l in cfg.get("extra_languages", []) if l.strip()]
    combined = list(LANGUAGES)
    for lang in extras:
        if lang not in combined:
            combined.append(lang)
    return combined

# ── Claude API ────────────────────────────────────────────────────────────────

def generate_sentences(api_key: str, word: str, language: str, cfg: dict) -> str:
    difficulty_map = {
        "beginner":     "simple vocabulary and short sentences (A1-A2 level)",
        "intermediate": "moderate complexity (B1-B2 level)",
        "advanced":     "rich, nuanced language (C1-C2 level)",
    }
    diff = difficulty_map.get(cfg["difficulty"], difficulty_map["intermediate"])
    n    = cfg["num_sentences"]
    translation_note = (
        " After each sentence add an English translation in parentheses."
        if cfg.get("include_translation") else ""
    )

    prompt = (
        f'Generate exactly {n} natural {language} example sentences using the word "{word}". '
        f"Use {diff}.{translation_note}\n\n"
        f'Bold the word "{word}" every time it appears using <b> tags. '
        f"Return only a numbered list, one sentence per line, no introduction."
    )

    payload = json.dumps({
        "model":      cfg["model"],
        "max_tokens": 1024,
        "messages":   [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())

    lines = [l.strip() for l in data["content"][0]["text"].strip().splitlines() if l.strip()]
    lines = [re.sub(r"^\d+\.\s*", "", l) for l in lines]
    spans = "".join(f'<span class="vsg-sentence" style="display:none">{l}</span>' for l in lines)
    return f'<div class="vsg-sentences">{spans}</div>'

# ── Language picker dialog ────────────────────────────────────────────────────

class GenerateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Sentences")
        self.setFixedWidth(260)
        self.chosen_language = None
        self._build_ui()

    def _build_ui(self):
        cfg = get_config()
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Select language:"))

        self.combo = QComboBox()
        for lang in get_language_list():
            self.combo.addItem(lang)
        default = cfg.get("default_language", "English")
        if default in get_language_list():
            self.combo.setCurrentText(default)
        layout.addWidget(self.combo)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _accept(self):
        self.chosen_language = self.combo.currentText()
        self.accept()

# ── Core action ───────────────────────────────────────────────────────────────

def run_generation(editor):
    cfg = get_config()

    api_key     = cfg["api_key"]
    word_field  = cfg["word_field"]
    front_field = cfg["front_field"]

    if not api_key:
        showWarning(
            "No Anthropic API key set.\n\n"
            "Go to Tools → Vocab Sentence Generator → Settings and add your key."
        )
        return

    note = editor.note
    if note is None:
        return

    if word_field not in note:
        showWarning(f'Word field "{word_field}" not found. Check Settings.')
        return
    if front_field not in note:
        showWarning(f'Front field "{front_field}" not found. Check Settings.')
        return

    word = note[word_field].strip()
    if not word:
        showWarning(f'The "{word_field}" field is empty. Enter a word first.')
        return

    # Show language picker
    dlg = GenerateDialog(editor.widget)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    language = dlg.chosen_language

    tooltip(f"Generating {language} sentences…", period=8000)
    QApplication.processEvents()

    try:
        html = generate_sentences(api_key, word, language, cfg)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        showWarning(f"API error {e.code}:\n{body}")
        return
    except Exception as ex:
        showWarning(f"Error generating sentences:\n{ex}")
        return

    note[front_field] = html

    try:
        editor.set_note(note)
    except Exception:
        try:
            note.flush()
            editor.loadNote()
        except Exception:
            editor.loadNote()

    tooltip(f"✓ {language} sentences generated!", period=2000)

# ── Editor toolbar button ─────────────────────────────────────────────────────

def setup_editor_button(buttons, editor):
    btn = editor.addButton(
        icon=None,
        cmd="vocab_gen",
        func=run_generation,
        tip="Generate example sentences (Vocab Sentence Generator)",
        label="✨ Generate",
    )
    buttons.append(btn)
    return buttons

# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("ScrambleSentences for language learning — Settings")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self):
        cfg = get_config()
        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.api_key_edit = QLineEdit(cfg["api_key"])
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("sk-ant-…")
        layout.addRow("Anthropic API key:", self.api_key_edit)

        self.word_field_edit  = QLineEdit(cfg["word_field"])
        self.front_field_edit = QLineEdit(cfg["front_field"])
        layout.addRow("Word field name:", self.word_field_edit)
        layout.addRow("Front field name:", self.front_field_edit)

        self.num_spin = QSpinBox()
        self.num_spin.setRange(1, 10)
        self.num_spin.setValue(cfg["num_sentences"])
        layout.addRow("Number of sentences:", self.num_spin)

        self.diff_combo = QComboBox()
        for d in ["beginner", "intermediate", "advanced"]:
            self.diff_combo.addItem(d)
        self.diff_combo.setCurrentText(cfg["difficulty"])
        layout.addRow("Difficulty:", self.diff_combo)

        self.default_lang_combo = QComboBox()
        for lang in get_language_list():
            self.default_lang_combo.addItem(lang)
        self.default_lang_combo.setCurrentText(cfg.get("default_language", "English"))
        layout.addRow("Default language:", self.default_lang_combo)

        self.extra_langs_edit = QLineEdit(", ".join(cfg.get("extra_languages", [])))
        self.extra_langs_edit.setPlaceholderText("e.g. Hindi, Vietnamese, Greek")
        layout.addRow("Extra languages:", self.extra_langs_edit)
        hint = QLabel("Comma-separated. Added to the language picker.")
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addRow(hint)

        self.trans_check = QCheckBox("Include English translation after each sentence")
        self.trans_check.setChecked(cfg["include_translation"])
        layout.addRow(self.trans_check)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def _save(self):
        extras = [l.strip() for l in self.extra_langs_edit.text().split(",") if l.strip()]
        save_config({
            "api_key":             self.api_key_edit.text().strip(),
            "word_field":          self.word_field_edit.text().strip() or DEFAULT_WORD_FIELD,
            "front_field":         self.front_field_edit.text().strip() or DEFAULT_FRONT_FIELD,
            "num_sentences":       self.num_spin.value(),
            "difficulty":          self.diff_combo.currentText(),
            "default_language":    self.default_lang_combo.currentText(),
            "extra_languages":     extras,
            "include_translation": self.trans_check.isChecked(),
        })
        tooltip("Settings saved.")
        self.accept()

# ── Menu ──────────────────────────────────────────────────────────────────────

def setup_menu():
    submenu = QMenu("ScrambleSentences", mw)
    mw.form.menuTools.addMenu(submenu)
    act = QAction("Settings…", mw)
    act.triggered.connect(lambda: SettingsDialog(mw).exec())
    submenu.addAction(act)

# ── Register hooks ────────────────────────────────────────────────────────────

gui_hooks.editor_did_init_buttons.append(setup_editor_button)
gui_hooks.main_window_did_init.append(setup_menu)
