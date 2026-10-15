from __future__ import annotations

"""Whisper / NLLB language code helpers."""

WHISPER_TO_NLLB: dict[str, str] = {
    "ru": "rus_Cyrl",
    "en": "eng_Latn",
    "de": "deu_Latn",
    "es": "spa_Latn",
    "fr": "fra_Latn",
    "it": "ita_Latn",
    "pt": "por_Latn",
    "uk": "ukr_Cyrl",
    "pl": "pol_Latn",
    "tr": "tur_Latn",
    "ar": "arb_Arab",
    "zh": "zho_Hans",
    "ja": "jpn_Jpan",
    "ko": "kor_Hang",
}


def whisper_lang_to_nllb(whisper_code: str) -> str:
    code = whisper_code.lower().split("-")[0]
    if code not in WHISPER_TO_NLLB:
        raise ValueError(
            f"Unsupported language {whisper_code!r}. "
            f"Add mapping in languages.WHISPER_TO_NLLB."
        )
    return WHISPER_TO_NLLB[code]


def target_subtitle_lang(config_value: str, detected: str) -> str:
    if config_value == "same":
        return detected.lower().split("-")[0]
    return config_value.lower().split("-")[0]
