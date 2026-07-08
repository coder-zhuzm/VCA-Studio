"""Stitch per-model full renders into a single merged vocal via ffmpeg.

Strategy (per the P1 plan): each model is inferred on the full vocal track,
then per-segment cuts are taken from the assigned model's render, faded at the
edges to avoid clicks, and concatenated. Multiple assigned models in one segment
are mixed at equal loudness. `mute` emits silence; `original` reuses the source
vocal. Cross-segment continuity is kept by edge fades.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import config


class StitchService:
    def __init__(self, ffmpeg_path: str = "") -> None:
        self._ffmpeg = str(ffmpeg_path or "").strip() or (shutil.which("ffmpeg") or "ffmpeg")

    def stitch(
        self,
        segments: list[dict[str, Any]],
        model_full_paths: dict[str, str],
        vocals_path: str,
        output_path: str,
        log_path: str,
    ) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        sr, ch = self._probe(vocals_path) if Path(vocals_path).is_file() else (44100, 2)

        with tempfile.TemporaryDirectory() as work_dir:
            clips: list[str] = []
            for idx, seg in enumerate(segments):
                start = float(seg.get("start") or 0)
                end = float(seg.get("end") or start)
                dur = max(end - start, 0.0)
                if dur <= 0:
                    continue
                clip = Path(work_dir) / f"seg_{idx:03d}.wav"
                self._render_segment(clip, seg, dur, sr, ch, model_full_paths, vocals_path, log_path)
                clips.append(str(clip))

            if not clips:
                raise RuntimeError("没有可拼接的片段。")
            list_file = Path(work_dir) / "list.txt"
            list_file.write_text("\n".join(f"file '{c}'" for c in clips), encoding="utf-8")
            self._run(
                [self._ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(output)],
                log_path,
            )
        if not output.is_file():
            raise RuntimeError("拼接未生成输出文件。")
        self._limit(output, log_path)
        return str(output)

    def _limit(self, path: Path, log_path: str) -> None:
        limited = path.with_suffix(".limited.wav")
        self._run(
            [self._ffmpeg, "-y", "-i", str(path), "-af", "alimiter=level_in=1:limit=0.8:asc=1:attack=5:release=50", str(limited)],
            log_path,
        )
        if limited.is_file():
            limited.replace(path)

    def _render_segment(self, clip: Path, seg: dict[str, Any], dur: float, sr: int, ch: int, model_full_paths: dict[str, str], vocals_path: str, log_path: str) -> None:
        mode = str(seg.get("mode") or "solo")
        if mode == "mute" or not seg.get("assigned_model_ids"):
            self._silence(clip, dur, sr, ch, log_path)
            return
        if mode == "original":
            self._cut(vocals_path, float(seg["start"]), dur, clip, float(seg.get("fade_in", 0)), float(seg.get("fade_out", 0)), log_path)
            return

        sources = [model_full_paths[mid] for mid in seg["assigned_model_ids"] if mid in model_full_paths]
        if not sources:
            self._silence(clip, dur, sr, ch, log_path)
            return
        if len(sources) == 1:
            self._cut(sources[0], float(seg["start"]), dur, clip, float(seg.get("fade_in", 0)), float(seg.get("fade_out", 0)), log_path)
            return
        cuts = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, src in enumerate(sources):
                cut = Path(tmp) / f"c{i}.wav"
                self._cut(src, float(seg["start"]), dur, cut, 0, 0, log_path)
                cuts.append(str(cut))
            self._mix(cuts, clip, float(seg.get("fade_in", 0)), float(seg.get("fade_out", 0)), log_path)

    def _cut(self, src: str, start: float, dur: float, out: Path, fade_in: float, fade_out: float, log_path: str) -> None:
        fade = self._fade_filter(fade_in, fade_out, dur)
        cmd = [self._ffmpeg, "-y", "-ss", f"{start:.4f}", "-t", f"{dur:.4f}", "-i", src]
        if fade:
            cmd += ["-af", fade]
        cmd += [str(out)]
        self._run(cmd, log_path)

    def _mix(self, sources: list[str], out: Path, fade_in: float, fade_out: float, log_path: str) -> None:
        count = len(sources)
        gain = 1 / (count ** 0.5)
        labels = "".join(f"[v{i}]" for i in range(count))
        head = "".join(f"[{i}:a]volume={gain:.4f}[v{i}];" for i in range(count))
        fade = self._fade_filter(fade_in, fade_out, None)
        tail = f"{labels}amix=inputs={count}:normalize=0"
        if fade:
            tail = f"{tail},{fade}"
        filter_complex = f"{head}{tail}"
        cmd = [self._ffmpeg, "-y", *sum((["-i", s] for s in sources), []), "-filter_complex", filter_complex, str(out)]
        self._run(cmd, log_path)

    def _silence(self, out: Path, dur: float, sr: int, ch: int, log_path: str) -> None:
        layout = "mono" if ch == 1 else "stereo"
        self._run(
            [self._ffmpeg, "-y", "-f", "lavfi", "-i", f"anullsrc=r={sr}:cl={layout}", "-t", f"{dur:.4f}", str(out)],
            log_path,
        )

    @staticmethod
    def _fade_filter(fade_in: float, fade_out: float, dur: float | None) -> str:
        parts: list[str] = []
        if fade_in > 0:
            parts.append(f"afade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0 and dur:
            parts.append(f"afade=t=out:st={max(dur - fade_out, 0):.3f}:d={fade_out:.3f}")
        return ",".join(parts)

    def _probe(self, path: str) -> tuple[int, int]:
        ffprobe = shutil.which("ffprobe") or "ffprobe"
        try:
            result = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=sample_rate,channels", "-of", "default=nw=1:nk=1", path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                **config.subprocess_no_window(),
            )
            lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            sr = int(lines[0]) if len(lines) > 0 else 44100
            ch = int(lines[1]) if len(lines) > 1 else 2
            return sr, ch
        except (OSError, subprocess.SubprocessError, ValueError):
            return 44100, 2

    def _run(self, command: list[str], log_path: str) -> None:
        try:
            with Path(log_path).open("a", encoding="utf-8") as log:
                log.write("Stitch: " + " ".join(command) + "\n")
                result = subprocess.run(
                    command,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    **config.subprocess_no_window(),
                )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(str(exc))
        if result.returncode != 0:
            raise RuntimeError(f"拼接失败，退出码 {result.returncode}")
