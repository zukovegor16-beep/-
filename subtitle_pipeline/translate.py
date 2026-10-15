from __future__ import annotations

from pathlib import Path

from subtitle_pipeline.config import TranslationConfig
from subtitle_pipeline.languages import whisper_lang_to_nllb
from subtitle_pipeline.srt_utils import SrtCue, read_srt, write_srt


class SrtTranslator:
    """Offline NLLB translation; timestamps unchanged."""

    def __init__(self, config: TranslationConfig):
        self._config = config
        self._tokenizer = None
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self._config.model_id)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self._config.model_id)

    def translate_cues(
        self,
        cues: list[SrtCue],
        source_whisper: str,
        target_whisper: str,
    ) -> list[SrtCue]:
        if source_whisper.split("-")[0] == target_whisper.split("-")[0]:
            return cues

        self._load()
        assert self._tokenizer is not None and self._model is not None

        src = whisper_lang_to_nllb(source_whisper)
        tgt = whisper_lang_to_nllb(target_whisper)
        self._tokenizer.src_lang = src

        translated: list[SrtCue] = []
        batch: list[str] = []
        batch_meta: list[SrtCue] = []

        def flush():
            nonlocal batch, batch_meta
            if not batch:
                return
            inputs = self._tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
            )
            forced_bos = self._tokenizer.convert_tokens_to_ids(tgt)
            outputs = self._model.generate(
                **inputs,
                forced_bos_token_id=forced_bos,
                max_new_tokens=self._config.max_new_tokens,
            )
            texts = self._tokenizer.batch_decode(outputs, skip_special_tokens=True)
            for cue, new_text in zip(batch_meta, texts):
                translated.append(
                    SrtCue(
                        index=cue.index,
                        start=cue.start,
                        end=cue.end,
                        text=new_text.strip(),
                    )
                )
            batch = []
            batch_meta = []

        for cue in cues:
            batch.append(cue.text.replace("\n", " "))
            batch_meta.append(cue)
            if len(batch) >= self._config.batch_size:
                flush()
        flush()
        return translated

    def translate_srt_file(
        self,
        input_srt: Path,
        output_srt: Path,
        source_whisper: str,
        target_whisper: str,
    ) -> Path:
        cues = read_srt(str(input_srt))
        out = self.translate_cues(cues, source_whisper, target_whisper)
        output_srt.parent.mkdir(parents=True, exist_ok=True)
        write_srt(str(output_srt), out)
        return output_srt
