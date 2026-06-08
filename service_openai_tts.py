"""
service_openai_tts.py — HyperTTS service plugin for OpenAI Text-to-Speech
=========================================================================
Drop into HyperTTS's services folder, then enable it in
Tools → HyperTTS: Services Configuration.

  Windows : %APPDATA%\\Anki2\\addons21\\111623432\\hypertts_addon\\services\\
  macOS   : ~/Library/Application Support/Anki2/addons21/111623432/hypertts_addon/services/
  Linux   : ~/.local/share/Anki2/addons21/111623432/hypertts_addon/services/

Works with the Vocab Sentence Generator: point HyperTTS at the "Front TTS"
field (written automatically if it exists on your note type) to generate audio
for the sentences on the front of your cards.
"""

import json
import urllib.request
import urllib.error
from typing import List

from hypertts_addon import service
from hypertts_addon import constants
from hypertts_addon import voice
from hypertts_addon import languages
from hypertts_addon import errors
from hypertts_addon import logging_utils

logger = logging_utils.get_child_logger(__name__)

_VOICES = [
    ("Alloy",   "alloy",   constants.Gender.Any,    [languages.AudioLanguage.en_US, languages.AudioLanguage.en_GB, languages.AudioLanguage.fr_FR, languages.AudioLanguage.de_DE, languages.AudioLanguage.es_ES, languages.AudioLanguage.ja_JP, languages.AudioLanguage.zh_CN, languages.AudioLanguage.pt_BR, languages.AudioLanguage.it_IT, languages.AudioLanguage.ko_KR]),
    ("Echo",    "echo",    constants.Gender.Male,   [languages.AudioLanguage.en_US, languages.AudioLanguage.en_GB, languages.AudioLanguage.fr_FR, languages.AudioLanguage.de_DE, languages.AudioLanguage.es_ES, languages.AudioLanguage.ja_JP, languages.AudioLanguage.zh_CN]),
    ("Fable",   "fable",   constants.Gender.Male,   [languages.AudioLanguage.en_US, languages.AudioLanguage.en_GB, languages.AudioLanguage.fr_FR, languages.AudioLanguage.de_DE, languages.AudioLanguage.es_ES]),
    ("Onyx",    "onyx",    constants.Gender.Male,   [languages.AudioLanguage.en_US, languages.AudioLanguage.en_GB, languages.AudioLanguage.fr_FR, languages.AudioLanguage.de_DE, languages.AudioLanguage.es_ES, languages.AudioLanguage.ja_JP, languages.AudioLanguage.zh_CN, languages.AudioLanguage.pt_BR, languages.AudioLanguage.it_IT, languages.AudioLanguage.ko_KR]),
    ("Nova",    "nova",    constants.Gender.Female, [languages.AudioLanguage.en_US, languages.AudioLanguage.en_GB, languages.AudioLanguage.fr_FR, languages.AudioLanguage.de_DE, languages.AudioLanguage.es_ES, languages.AudioLanguage.ja_JP, languages.AudioLanguage.zh_CN, languages.AudioLanguage.pt_BR, languages.AudioLanguage.it_IT, languages.AudioLanguage.ko_KR]),
    ("Shimmer", "shimmer", constants.Gender.Female, [languages.AudioLanguage.en_US, languages.AudioLanguage.en_GB, languages.AudioLanguage.fr_FR, languages.AudioLanguage.de_DE, languages.AudioLanguage.es_ES, languages.AudioLanguage.ja_JP, languages.AudioLanguage.zh_CN, languages.AudioLanguage.pt_BR, languages.AudioLanguage.it_IT, languages.AudioLanguage.ko_KR]),
]

_OPTIONS = {
    "model": {"type": "list",   "values": ["tts-1", "tts-1-hd"], "default": "tts-1"},
    "speed": {"type": "number", "min": 0.25, "max": 4.0,         "default": 1.0},
}


class OpenAITTS(service.ServiceBase):
    CONFIG_API_KEY  = "api_key"
    CONFIG_BASE_URL = "base_url"

    def __init__(self):
        service.ServiceBase.__init__(self)

    @property
    def service_type(self):
        return constants.ServiceType.tts

    @property
    def service_fee(self):
        return constants.ServiceFee.paid

    def configuration_options(self):
        return {self.CONFIG_API_KEY: str, self.CONFIG_BASE_URL: str}

    def configure(self, config):
        self._api_key  = self.get_configuration_value_mandatory(self.CONFIG_API_KEY)
        self._base_url = (self.get_configuration_value_optional(self.CONFIG_BASE_URL, "").strip().rstrip("/") or "https://api.openai.com/v1")

    def enabled_by_default(self):
        return False

    def voice_list(self) -> List[voice.TtsVoice_v3]:
        return [
            voice.TtsVoice_v3(
                name=f"OpenAI {name}", voice_key={"voice": vid},
                options=_OPTIONS, service=self.name,
                gender=gender, audio_languages=langs,
                service_fee=self.service_fee,
            )
            for (name, vid, gender, langs) in _VOICES
        ]

    def get_tts_audio(self, source_text, tts_voice, voice_options) -> bytes:
        payload = json.dumps({
            "model":           voice_options.get("model",  "tts-1"),
            "input":           source_text,
            "voice":           tts_voice.voice_key["voice"],
            "speed":           float(voice_options.get("speed", 1.0)),
            "response_format": "mp3",
        }).encode()

        req = urllib.request.Request(
            f"{self._base_url}/audio/speech",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
        except urllib.error.HTTPError as e:
            raise errors.RequestError(source_text, tts_voice, f"HTTP {e.code}: {e.read().decode(errors='replace')}")
        except Exception as ex:
            raise errors.RequestError(source_text, tts_voice, str(ex))

        if len(data) < 100:
            raise errors.AudioNotFoundError(source_text, tts_voice)
        return data
