"""
ScrambleSentences for language learning — Anki Add-on

- Supports Anthropic (Claude) and OpenAI as generation providers
- Reads the Word field, generates example sentences, stores all in Front
- At generation time picks one sentence for Front TTS + Front TTS Date
- card_will_show: same sentence all day, new sentence each new day
- AwesomeTTS reads Front TTS (always a static plain-text value)
"""

import json
import re
import random
from datetime import date
import urllib.request
import urllib.error
from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.utils import showWarning, tooltip

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_WORD_FIELD  = "Word"
DEFAULT_FRONT_FIELD = "Front"
TTS_FIELD           = "Front TTS"
TTS_DATE_FIELD      = "Front TTS Date"
DATE_FORMAT         = "%Y-%m-%d"

PROVIDERS = ["Anthropic (Claude)", "OpenAI"]

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-5"
DEFAULT_OPENAI_MODEL    = "gpt-4o"

LANGUAGES = [
    "English", "Spanish", "French", "German", "Italian",
    "Portuguese", "Japanese", "Chinese", "Korean", "Arabic",
    "Russian", "Dutch", "Polish", "Turkish", "Swedish",
]

# ── Config ────────────────────────────────────────────────────────────────────

def get_config():
    cfg = mw.addonManager.getConfig(__name__) or {}
    return {
        # Provider selection
        "provider":              cfg.get("provider", "Anthropic (Claude)"),
        # Anthropic settings
        "anthropic_api_key":     cfg.get("anthropic_api_key", cfg.get("api_key", "")),
        "anthropic_model":       cfg.get("anthropic_model", DEFAULT_ANTHROPIC_MODEL),
        # OpenAI settings
        "openai_api_key":        cfg.get("openai_api_key", ""),
        "openai_model":          cfg.get("openai_model", DEFAULT_OPENAI_MODEL),
        # Shared settings
        "word_field":            cfg.get("word_field", DEFAULT_WORD_FIELD),
        "front_field":           cfg.get("front_field", DEFAULT_FRONT_FIELD),
        "num_sentences":         cfg.get("num_sentences", 3),
        "default_language":      cfg.get("default_language", "English"),
        "difficulty":            cfg.get("difficulty", "intermediate"),
        "include_translation":   cfg.get("include_translation", False),
        "extra_languages":       cfg.get("extra_languages", []),
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

# ── Sentence helpers ──────────────────────────────────────────────────────────

def _today() -> str:
    return date.today().strftime(DATE_FORMAT)

def _extract_sentences(html: str) -> list:
    return re.findall(
        r'<span class="vsg-sentence"[^>]*>(.*?)</span>',
        html, re.DOTALL,
    )

def _plain(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()

def _write_tts(note, sentence_html: str):
    if TTS_FIELD in note:
        note[TTS_FIELD] = _plain(sentence_html)
    if TTS_DATE_FIELD in note:
        note[TTS_DATE_FIELD] = _today()

# ── card_will_show hook ───────────────────────────────────────────────────────

def on_card_will_show(html: str, card, kind: str) -> str:
    if "vsg-sentence" not in html:
        return html

    sentences = _extract_sentences(html)
    if not sentences:
        return html

    try:
        note = card.note()
        today = _today()
        stored_date = note[TTS_DATE_FIELD] if TTS_DATE_FIELD in note else ""
        stored_tts  = note[TTS_FIELD]      if TTS_FIELD in note      else ""

        chosen = None
        if stored_date == today and stored_tts:
            for s in sentences:
                if _plain(s) == stored_tts:
                    chosen = s
                    break

        if chosen is None:
            chosen = random.choice(sentences)
            _write_tts(note, chosen)
            note.flush()

    except Exception:
        chosen = random.choice(sentences)

    plain_chosen = _plain(chosen)

    # Replace the vsg-sentences block with just the chosen sentence
    html = re.sub(
        r'<div class="vsg-sentences">.*?</div>',
        f'<div class="vsg-sentences">{chosen}</div>',
        html, flags=re.DOTALL,
    )

    # Also replace the content inside any <tts> tag so AwesomeTTS reads
    # the correct sentence. Anki resolves {{Front TTS}} before this hook
    # runs, so the HTML still has the old/empty text baked in.
    html = re.sub(
        r'(<tts\b[^>]*>)(.*?)(</tts>)',
        rf'\g<1>{plain_chosen}\g<3>',
        html, flags=re.DOTALL,
    )

    return html

gui_hooks.card_will_show.append(on_card_will_show)

# ── API calls ─────────────────────────────────────────────────────────────────

def _build_prompt(word: str, language: str, cfg: dict) -> str:
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
    return (
        f'Generate exactly {n} natural {language} example sentences using the word "{word}". '
        f"Use {diff}.{translation_note}\n\n"
        f'Bold the word "{word}" every time it appears using <b> tags. '
        f"Return only a numbered list, one sentence per line, no introduction."
    )

def _parse_lines(raw_text: str) -> list:
    lines = [l.strip() for l in raw_text.strip().splitlines() if l.strip()]
    lines = [re.sub(r"^\d+\.\s*", "", l) for l in lines]
    # Convert markdown bold **word** to HTML <b>word</b>
    lines = [re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", l) for l in lines]
    return lines

def _call_anthropic(prompt: str, cfg: dict) -> list:
    payload = json.dumps({
        "model":      cfg["anthropic_model"],
        "max_tokens": 1024,
        "messages":   [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         cfg["anthropic_api_key"],
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return _parse_lines(data["content"][0]["text"])

def _call_openai(prompt: str, cfg: dict) -> list:
    payload = json.dumps({
        "model":    cfg["openai_model"],
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {cfg['openai_api_key']}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return _parse_lines(data["choices"][0]["message"]["content"])

def generate_sentences(word: str, language: str, cfg: dict) -> tuple:
    """Returns (html, lines). Dispatches to the configured provider."""
    prompt = _build_prompt(word, language, cfg)

    if cfg["provider"] == "OpenAI":
        if not cfg["openai_api_key"]:
            raise ValueError("No OpenAI API key set. Go to Settings and add your key.")
        lines = _call_openai(prompt, cfg)
    else:
        if not cfg["anthropic_api_key"]:
            raise ValueError("No Anthropic API key set. Go to Settings and add your key.")
        lines = _call_anthropic(prompt, cfg)

    spans = "".join(
        f'<span class="vsg-sentence" style="display:none">{l}</span>'
        for l in lines
    )
    return f'<div class="vsg-sentences">{spans}</div>', lines

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
    word_field  = cfg["word_field"]
    front_field = cfg["front_field"]

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

    dlg = GenerateDialog(editor.widget)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    language = dlg.chosen_language

    tooltip(f"Generating {language} sentences…", period=8000)
    QApplication.processEvents()

    try:
        html, lines = generate_sentences(word, language, cfg)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        showWarning(f"API error {e.code}:\n{body}")
        return
    except ValueError as e:
        showWarning(str(e))
        return
    except Exception as ex:
        showWarning(f"Error generating sentences:\n{ex}")
        return

    note[front_field] = html

    if lines:
        chosen_html = random.choice([
            f'<span class="vsg-sentence" style="display:none">{l}</span>'
            for l in lines
        ])
        _write_tts(note, chosen_html)

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
        tip="Generate example sentences (ScrambleSentences for language learning)",
        label="✨ Generate",
    )
    buttons.append(btn)
    return buttons

# ── Settings dialog ───────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.setWindowTitle("ScrambleSentences for language learning — Settings")
        self.setMinimumWidth(440)
        self._build_ui()

    def _build_ui(self):
        cfg = get_config()
        layout = QFormLayout(self)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # ── Provider ──
        provider_label = QLabel("<b>Provider</b>")
        layout.addRow(provider_label)

        self.provider_combo = QComboBox()
        for p in PROVIDERS:
            self.provider_combo.addItem(p)
        self.provider_combo.setCurrentText(cfg.get("provider", "Anthropic (Claude)"))
        self.provider_combo.currentTextChanged.connect(self._update_provider_visibility)
        layout.addRow("Provider:", self.provider_combo)

        # ── Anthropic ──
        self.anthropic_label = QLabel("<b>Anthropic settings</b>")
        layout.addRow(self.anthropic_label)

        self.anthropic_key_edit = QLineEdit(cfg["anthropic_api_key"])
        self.anthropic_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_key_edit.setPlaceholderText("sk-ant-…")
        self.anthropic_key_row_label = QLabel("Anthropic API key:")
        layout.addRow(self.anthropic_key_row_label, self.anthropic_key_edit)

        self.anthropic_model_edit = QLineEdit(cfg["anthropic_model"])
        self.anthropic_model_row_label = QLabel("Anthropic model:")
        layout.addRow(self.anthropic_model_row_label, self.anthropic_model_edit)

        # ── OpenAI ──
        self.openai_label = QLabel("<b>OpenAI settings</b>")
        layout.addRow(self.openai_label)

        self.openai_key_edit = QLineEdit(cfg["openai_api_key"])
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setPlaceholderText("sk-…")
        self.openai_key_row_label = QLabel("OpenAI API key:")
        layout.addRow(self.openai_key_row_label, self.openai_key_edit)

        self.openai_model_edit = QLineEdit(cfg["openai_model"])
        self.openai_model_row_label = QLabel("OpenAI model:")
        layout.addRow(self.openai_model_row_label, self.openai_model_edit)

        # ── Fields ──
        layout.addRow(QLabel("<b>Note fields</b>"))
        self.word_field_edit  = QLineEdit(cfg["word_field"])
        self.front_field_edit = QLineEdit(cfg["front_field"])
        layout.addRow("Word field name:", self.word_field_edit)
        layout.addRow("Front field name:", self.front_field_edit)

        # ── Generation options ──
        layout.addRow(QLabel("<b>Generation options</b>"))

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

        # Set initial visibility
        self._update_provider_visibility(cfg.get("provider", "Anthropic (Claude)"))

    def _update_provider_visibility(self, provider: str):
        is_anthropic = provider == "Anthropic (Claude)"
        for w in [self.anthropic_label, self.anthropic_key_edit,
                  self.anthropic_key_row_label, self.anthropic_model_edit,
                  self.anthropic_model_row_label]:
            w.setVisible(is_anthropic)
        for w in [self.openai_label, self.openai_key_edit,
                  self.openai_key_row_label, self.openai_model_edit,
                  self.openai_model_row_label]:
            w.setVisible(not is_anthropic)

    def _save(self):
        extras = [l.strip() for l in self.extra_langs_edit.text().split(",") if l.strip()]
        save_config({
            "provider":            self.provider_combo.currentText(),
            "anthropic_api_key":   self.anthropic_key_edit.text().strip(),
            "anthropic_model":     self.anthropic_model_edit.text().strip() or DEFAULT_ANTHROPIC_MODEL,
            "openai_api_key":      self.openai_key_edit.text().strip(),
            "openai_model":        self.openai_model_edit.text().strip() or DEFAULT_OPENAI_MODEL,
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
    submenu = QMenu("ScrambleSentences for language learning", mw)
    mw.form.menuTools.addMenu(submenu)
    act = QAction("Settings…", mw)
    act.triggered.connect(lambda: SettingsDialog(mw).exec())
    submenu.addAction(act)

# ── Register hooks ────────────────────────────────────────────────────────────

gui_hooks.editor_did_init_buttons.append(setup_editor_button)
gui_hooks.main_window_did_init.append(setup_menu)
