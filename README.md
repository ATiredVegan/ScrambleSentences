# ScrambleSentences for language learning

Ever memorize the content of a sentence mining card rather than the word you're trying to memorize? Look no further. ScrambleSentences generates random sentences for a user-given vocabulary word, and then randomly cycles through them every time you review the card. That way you're memorizing the word rather than the context of the sentence. 


---

## How it works

1. Type a vocabulary word into the **Word** field
2. Click **✨ Generate** in the editor toolbar
3. Pick a language from the popup and hit OK
4. The **Front** field fills with AI-generated sentences (word bolded)
5. Fill in **Back** manually and save the card

During review, one sentence is shown at random. The same sentence is shown all day — on a new day a different one is picked automatically.

---

## Installation

Copy the `ScrambleSentences` folder into your Anki add-ons directory and restart Anki:

| OS | Path |
|----|------|
| Windows | `%APPDATA%\Anki2\addons21\` |
| macOS | `~/Library/Application Support/Anki2/addons21/` |
| Linux | `~/.local/share/Anki2/addons21/` |

---

## Required note fields

Your note type must have these fields:

| Field | Purpose |
|-------|---------|
| `Word` | The vocabulary word you type in |
| `Front` | Receives the AI-generated sentences (HTML) |
| `Back` | You fill this in manually |

### Optional TTS fields

If you want AwesomeTTS to read the displayed sentence aloud, add these two fields:

| Field | Purpose |
|-------|---------|
| `Front TTS` | Plain-text version of the chosen sentence (read by AwesomeTTS) |
| `Front TTS Date` | Stores the date the sentence was last picked (used internally) |

These fields do not need to appear on your card template — they just need to exist on the note type.

### Recommended note type layout

```
Word           ← you type the vocab word here
Front          ← AI-generated sentences (displayed on card)
Back           ← you fill in manually
Front TTS      ← plain text for AwesomeTTS (optional)
Front TTS Date ← internal date tracking (optional)
```

### Card template

Your Front template only needs:

```html
{{Front}}
```

No JavaScript required — sentence selection is handled by the add-on.

If using AwesomeTTS, add to your Front template:

```html
{{Front}}
<tts service="google" voice="en">{{Front TTS}}</tts>
```

---

## Setup

Go to **Tools → ScrambleSentences for language learning → Settings**

### Provider

Choose between **Anthropic (Claude)** (default) or **OpenAI**.

#### Anthropic

| Setting | Default | Description |
|---------|---------|-------------|
| Anthropic API key | — | Get one at https://console.anthropic.com (starts with `sk-ant-`) |
| Anthropic model | `claude-sonnet-4-5` | Claude model to use |

#### OpenAI

| Setting | Default | Description |
|---------|---------|-------------|
| OpenAI API key | — | Get one at https://platform.openai.com (starts with `sk-`) |
| OpenAI model | `gpt-4o` | OpenAI model to use |

### Generation options

| Setting | Default | Description |
|---------|---------|-------------|
| Word field name | `Word` | Field containing the vocabulary word |
| Front field name | `Front` | Field that receives the generated sentences |
| Number of sentences | `3` | How many sentences to generate (1–10) |
| Difficulty | `intermediate` | `beginner` / `intermediate` / `advanced` |
| Default language | `English` | Pre-selected language in the picker |
| Extra languages | — | Comma-separated list of additional languages to add to the picker |
| Include translation | off | Appends an English translation after each sentence |

---

## Supported languages

English, Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Korean, Arabic, Russian, Dutch, Polish, Turkish, Swedish — plus any languages you add via **Extra languages** in Settings.

---

## HyperTTS / OpenAI TTS (optional)

The zip includes `service_openai_tts.py`, a HyperTTS service plugin that adds OpenAI TTS voices. To install:

1. Copy `service_openai_tts.py` into the HyperTTS services folder:

   | OS | Path |
   |----|------|
   | Windows | `%APPDATA%\Anki2\addons21\111623432\hypertts_addon\services\` |
   | macOS | `~/Library/Application Support/Anki2/addons21/111623432/hypertts_addon/services/` |
   | Linux | `~/.local/share/Anki2/addons21/111623432/hypertts_addon/services/` |

2. Restart Anki
3. Go to **Tools → HyperTTS: Services Configuration**, enable **OpenAI TTS**, and enter your OpenAI API key

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| API error 401 | Wrong or missing API key for the selected provider |
| API error 404 | Wrong model name — check the model string in Settings |
| API error 429 | Rate limit hit — wait a moment and try again |
| No sentence shown on card | Make sure your Front template contains `{{Front}}` |
| AwesomeTTS reads wrong sentence | Ensure `Front TTS` and `Front TTS Date` fields exist on your note type |
