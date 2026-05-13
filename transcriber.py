import threading
import numpy as np
from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size: str = "tiny", language: str | None = None):
        self._model: WhisperModel | None = None
        self._model_size = model_size
        self._language = language
        self._ready = threading.Event()
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> None:
        print(f"[FreeWhisper] Loading {self._model_size} model…")
        self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
        print("[FreeWhisper] Model ready.")
        self._ready.set()

    def transcribe(self, audio: np.ndarray) -> str:
        self._ready.wait()  # block until model has finished loading
        if audio.size == 0:
            return ""
        segments, _ = self._model.transcribe(audio, beam_size=5, language=self._language)
        return " ".join(seg.text.strip() for seg in segments).strip()
