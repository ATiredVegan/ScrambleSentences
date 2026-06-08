# ScrambleSentences for language learning

Type a word → click **✨ Generate** → the **Front** field fills with AI-generated example sentences with the word bolded. Fill in **Back** yourself.

---

## Installation

Copy the `vocab_sentence_generator/` folder into your Anki add-ons directory and restart Anki:

| OS | Path |
|----|------|
| Windows | `%APPDATA%\Anki2\addons21\` |
| macOS | `~/Library/Application Support/Anki2/addons21/` |
| Linux | `~/.local/share/Anki2/addons21/` |

---

## Setup

1. Get an Anthropic API key at https://console.anthropic.com
2. In Anki: **Tools → Vocab Sentence Generator → Settings**
3. Paste your API key and save

Default field names are **Word** (source) and **Front** (destination). Change them in Settings if your note type uses different names.

---

## Usage

1. Open the **Add** dialog
2. Type the vocabulary word into the **Word** field
3. Click **✨ Generate** in the editor toolbar
4. The **Front** field is filled with numbered sentences, word bolded
5. Fill in **Back** manually and save the card

---

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| API key | — | Your Anthropic API key |
| Word field | `Word` | Field containing the vocabulary word |
| Front field | `Front` | Field that receives the generated sentences |
| Language | `English` | Language for sentences |
| Number of sentences | `3` | How many sentences to generate (1–10) |
| Difficulty | `intermediate` | `beginner` / `intermediate` / `advanced` |
| Include translation | off | Adds an English translation after each sentence |

---

## HyperTTS integration (optional)

If your note type has a field called **`Front TTS`**, the add-on automatically writes a plain-text version of the sentences there (no HTML, no numbering). Point HyperTTS at that field to generate audio pronunciation for the sentences.

To add the OpenAI TTS voice service to HyperTTS:

1. Copy `service_openai_tts.py` into HyperTTS's services folder:

   | OS | Path |
   |----|------|
   | Windows | `%APPDATA%\Anki2\addons21\111623432\hypertts_addon\services\` |
   | macOS | `~/Library/Application Support/Anki2/addons21/111623432/hypertts_addon/services/` |
   | Linux | `~/.local/share/Anki2/addons21/111623432/hypertts_addon/services/` |

2. Restart Anki
3. **Tools → HyperTTS: Services Configuration** → enable **OpenAI TTS** → enter your OpenAI API key

Voices: Alloy, Echo, Fable, Onyx, Nova, Shimmer — with standard and HD quality options.
