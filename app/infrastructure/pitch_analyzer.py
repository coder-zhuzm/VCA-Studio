"""Basic monophonic pitch tracking -> coarse MIDI notes.

A dependency-free implementation intended as the MVP for "Vocal to MIDI &
Lyrics" (阶段 6). It normalizes the input to mono 16-bit via ffmpeg, then runs
autocorrelation-based fundamental estimation frame by frame and merges stable
pitch regions into notes. This is intentionally coarse; swap in RMVPE/CREPE/
Basic Pitch later without changing the `analyze` contract.
"""

from __future__ import annotations

import array
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import config


class PitchAnalyzer:
    def __init__(self, ffmpeg_path: str = "") -> None:
        self._ffmpeg = str(ffmpeg_path or "").strip() or (shutil.which("ffmpeg") or "ffmpeg")

    def analyze(self, wav_path: str, log_path: str = "") -> dict[str, Any]:
        wav = Path(wav_path)
        if not wav.is_file():
            return {"ok": False, "error": "音高解析缺少输入音频。"}
        with tempfile.TemporaryDirectory() as tmp:
            mono = Path(tmp) / "mono.wav"
            if not self._normalize(wav, mono, log_path):
                return {"ok": False, "error": "音高解析音频归一化失败。"}
            frames = self._read_mono(mono)
            notes = self._track(str(mono), frames)
        return {"ok": True, "notes": notes, "duration": self._duration(notes)}

    def _normalize(self, src: Path, dst: Path, log_path: str) -> bool:
        try:
            with Path(log_path or Path(src).with_suffix(".log")).open("a", encoding="utf-8") as log:
                log.write(f"Pitch: normalize {src} -> {dst}\n")
                result = subprocess.run(
                    [self._ffmpeg, "-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-f", "wav", str(dst)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                    **config.subprocess_no_window(),
                )
            return result.returncode == 0 and dst.is_file()
        except (OSError, subprocess.SubprocessError):
            return False

    @staticmethod
    def _read_mono(path: Path) -> tuple[list[float], int]:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            n = wav.getnframes()
            raw = wav.readframes(n)
        samples = array.array("h")
        samples.frombytes(raw)
        if wav.getnchannels() > 1:
            samples = array.array("h", [sum(samples[i::wav.getnchannels()]) // wav.getnchannels() for i in range(len(samples) // wav.getnchannels())])
        return [s / 32768.0 for s in samples], rate

    def _track(self, path: str, frames: tuple[list[float], int]) -> list[dict[str, Any]]:
        signal, rate = frames
        frame_size = 1024
        hop = 256
        min_lag = max(1, int(rate / 1000))  # up to ~1000 Hz
        max_lag = int(rate / 60)  # down to ~60 Hz
        notes: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None
        for start in range(0, max(1, len(signal) - frame_size), hop):
            frame = signal[start : start + frame_size]
            freq, confidence = self._pitch(frame, rate, min_lag, max_lag)
            t = start / rate
            if freq is None or confidence < 0.4:
                if current:
                    current["end"] = t
                    notes.append(current)
                    current = None
                continue
            midi = round(69 + 12 * math.log2(freq / 440))
            if current and current["midi"] == midi:
                current["end"] = t + frame_size / rate
            else:
                if current:
                    current["end"] = t
                    notes.append(current)
                current = {"start": t, "end": t + frame_size / rate, "midi": midi, "freq": round(freq, 2)}
        if current:
            notes.append(current)
        return notes

    @staticmethod
    def _pitch(frame: list[float], rate: int, min_lag: int, max_lag: int) -> tuple[float | None, float]:
        energy = sum(x * x for x in frame)
        if energy < 1e-4:
            return None, 0.0
        best_lag = 0
        best_corr = 0.0
        for lag in range(min_lag, min(max_lag, len(frame) - 1)):
            corr = sum(frame[i] * frame[i + lag] for i in range(len(frame) - lag))
            corr /= energy
            if corr > best_corr:
                best_corr = corr
                best_lag = lag
        if best_lag == 0:
            return None, 0.0
        return rate / best_lag, best_corr

    @staticmethod
    def _duration(notes: list[dict[str, Any]]) -> float:
        if not notes:
            return 0.0
        return round(notes[-1]["end"], 3)


def align_lyrics(lyrics: list[str], notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Naive uniform alignment: spread lyric lines evenly across the notes span."""
    lines = [line.strip() for line in lyrics if line.strip()]
    if not lines or not notes:
        return []
    start = notes[0]["start"]
    end = notes[-1]["end"]
    span = max(end - start, 0.0)
    per = span / len(lines)
    return [
        {"start": round(start + i * per, 3), "end": round(start + (i + 1) * per, 3), "text": line}
        for i, line in enumerate(lines)
    ]
