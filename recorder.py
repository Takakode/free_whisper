import logging
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger(__name__)


class Recorder:
    SAMPLE_RATE = 16_000

    def __init__(self):
        self._chunks: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None

    def start(self) -> None:
        self._chunks = []
        self._recording = True

        def callback(indata, frames, time, status):
            if status:
                log.warning("Audio capture issue: %s", status)
            if self._recording:
                with self._lock:
                    self._chunks.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if self._chunks:
                audio = np.concatenate(self._chunks, axis=0).flatten()
                # Clear chunks from memory once consumed
                self._chunks = []
                return audio
        return np.array([], dtype="float32")
