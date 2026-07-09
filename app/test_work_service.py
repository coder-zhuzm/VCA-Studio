from __future__ import annotations

import tempfile
from pathlib import Path
from time import monotonic
from unittest.mock import patch

import shutil
import subprocess

from application.inference_runner import InferenceRunner
from application.stem_preparer import StemPreparer
from application.stitch_service import StitchService
from application.work_service import WorkService
from infrastructure.engine import EngineRegistry
from infrastructure.storage import ListRepository


class FakeRunner:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    def run_rvc(self, work, model, vocals_path, out_path=None):
        if not self.ok:
            return {"ok": False, "error": "boom"}
        out = Path(out_path) if out_path else Path(work["work_dir"]) / "inference" / "ai_vocal.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(out)
        return {"ok": True, "path": str(out)}

    @staticmethod
    def _write_wav(out: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            try:
                subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", str(out)], capture_output=True, check=True)
                return
            except (OSError, subprocess.SubprocessError):
                pass
        out.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")


def _service(tmp: Path, ok: bool, stems: bool = False) -> tuple[WorkService, str]:
    tmp.mkdir(parents=True)
    model_file = tmp / "model.pth"
    vocal_file = tmp / "vocals.wav"
    instrumental_file = tmp / "instrumental.wav"
    model_file.write_bytes(b"model")
    vocal_file.write_bytes(b"audio")
    instrumental_file.write_bytes(b"music")

    model_repo = ListRepository(tmp / "models.json")
    work_repo = ListRepository(tmp / "works.json")
    model_repo.add({"id": "m1", "framework": "rvc", "files": {"checkpoint": str(model_file)}})
    work = {
        "id": "w1",
        "model_id": "m1",
        "params": {},
        "input_mode": "stems" if stems else "vocals",
        "input_files": [
            {"role": "vocals", "stored_path": str(vocal_file)},
            *([{"role": "instrumental", "stored_path": str(instrumental_file)}] if stems else []),
        ],
        "status": "pending",
        "stage": "prepared",
        "progress": 10,
        "steps": [],
        "logs": [],
        "work_dir": str(tmp / "work_w1"),
        "log_path": str(tmp / "work_w1" / "run.log"),
    }
    work_repo.add(work)
    return WorkService(work_repo, StemPreparer(tmp / "works", shutil.which("ffmpeg") or ""), model_repo, None, FakeRunner(ok)), "w1"


def _service_song(tmp: Path, ok: bool) -> tuple[WorkService, str]:
    tmp.mkdir(parents=True)
    model_file = tmp / "model.pth"
    song_file = tmp / "song.wav"
    model_file.write_bytes(b"model")
    song_file.write_bytes(b"audio")

    model_repo = ListRepository(tmp / "models.json")
    work_repo = ListRepository(tmp / "works.json")
    model_repo.add({"id": "m1", "framework": "rvc", "files": {"checkpoint": str(model_file)}})
    work = {
        "id": "w1",
        "model_id": "m1",
        "params": {},
        "input_mode": "song",
        "skip_dereverb": True,
        "input_files": [
            {"role": "input_song", "source_path": str(song_file), "stored_path": str(song_file), "filename": "song.wav"},
        ],
        "status": "pending",
        "stage": "prepared",
        "progress": 10,
        "steps": [],
        "logs": [],
        "work_dir": str(tmp / "work_w1"),
        "log_path": str(tmp / "work_w1" / "run.log"),
    }
    work_repo.add(work)
    return WorkService(work_repo, StemPreparer(tmp / "works", shutil.which("ffmpeg") or ""), model_repo, None, FakeRunner(ok)), "w1"


def _service_multi(tmp: Path, ok: bool) -> tuple[WorkService, str]:
    tmp.mkdir(parents=True)
    model_a = tmp / "model_a.pth"
    model_b = tmp / "model_b.pth"
    vocal_file = tmp / "vocals.wav"
    model_a.write_bytes(b"model")
    model_b.write_bytes(b"model")
    vocal_file.write_bytes(b"audio")

    model_repo = ListRepository(tmp / "models.json")
    work_repo = ListRepository(tmp / "works.json")
    model_repo.add({"id": "ma", "framework": "rvc", "files": {"checkpoint": str(model_a)}})
    model_repo.add({"id": "mb", "framework": "rvc", "files": {"checkpoint": str(model_b)}})
    work = {
        "id": "w1",
        "model_id": "ma",
        "models": [
            {"model_id": "ma", "params": {}},
            {"model_id": "mb", "params": {}},
        ],
        "params": {},
        "segments": [
            {"id": "seg_001", "start": 0, "end": 1, "text": "A", "assigned_model_ids": ["ma"], "mode": "solo"},
            {"id": "seg_002", "start": 1, "end": 2, "text": "B", "assigned_model_ids": ["mb"], "mode": "solo"},
        ],
        "input_mode": "vocals",
        "input_files": [
            {"role": "vocals", "stored_path": str(vocal_file)},
        ],
        "status": "pending",
        "stage": "prepared",
        "progress": 10,
        "steps": [],
        "logs": [],
        "work_dir": str(tmp / "work_w1"),
        "log_path": str(tmp / "work_w1" / "run.log"),
    }
    work_repo.add(work)
    return WorkService(work_repo, StemPreparer(tmp / "works", shutil.which("ffmpeg") or ""), model_repo, None, FakeRunner(ok)), "w1"


def wait_for(service: WorkService, work_id: str, status: str):
    deadline = monotonic() + 5
    while monotonic() < deadline:
        work = service.get_work(work_id)["work"]
        if work["status"] == status:
            return work
    raise AssertionError(f"work did not reach {status}")


def smoke() -> None:
    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service(Path(root) / "ok", True)
        work = service.start_work(work_id)["work"]
        assert work["status"] == "running"
        work = wait_for(service, work_id, "done")
        assert work["status"] == "done"
        assert work["stage"] == "exported"
        assert work["progress"] == 100
        assert Path(work["output_files"]["final"]).is_file()
        assert [step["status"] for step in work["steps"] if step["key"] == "run"] == ["done"]

    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service(Path(root) / "stems", True, stems=True)
        with patch("application.work_service.subprocess.run") as run:
            run.side_effect = lambda *_, **__: Path(service._repo.get(work_id)["work_dir"]).joinpath("output", "final.wav").write_bytes(b"mix")
            work = service.start_work(work_id)["work"]
            assert work["status"] == "running"
            work = wait_for(service, work_id, "done")
        assert work["status"] == "done"
        assert Path(work["output_files"]["final"]).is_file()
        assert any("amix" in str(call.args) for call in run.call_args_list)

    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service(Path(root) / "mixblock", True, stems=True)
        service._stem_preparer._ffmpeg_path = ""
        with patch("application.work_service.shutil.which", return_value=None):
            work = service.start_work(work_id)["work"]
        assert work["status"] == "failed"
        assert "ffmpeg" in work["logs"][-1]["message"]

    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service(Path(root) / "fail", False)
        work = service.start_work(work_id)["work"]
        assert work["status"] == "running"
        work = wait_for(service, work_id, "failed")
        assert work["stage"] == "failed"
        assert work["logs"][-1]["message"] == "boom"
        assert [step["status"] for step in work["steps"] if step["key"] == "run"] == ["failed"]

    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service_song(Path(root) / "song", True)
        work = service.start_work(work_id)["work"]
        assert work["status"] == "running"
        work = wait_for(service, work_id, "done")
        assert work["status"] == "done"
        assert [step["status"] for step in work["steps"] if step["key"] == "separate"] == ["done"]
        assert [step["status"] for step in work["steps"] if step["key"] == "run"] == ["done"]
        assert Path(work["output_files"]["final"]).is_file()

    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service_multi(Path(root) / "multi", True)
        work = service.start_work(work_id)["work"]
        assert work["status"] == "running"
        work = wait_for(service, work_id, "done")
        assert work["status"] == "done"
        assert [step["status"] for step in work["steps"] if step["key"] == "run"] == ["done"]
        assert Path(work["work_dir"]).joinpath("renders", "ma", "full.wav").is_file()
        assert Path(work["work_dir"]).joinpath("renders", "mb", "full.wav").is_file()
        assert Path(work["output_files"]["final"]).is_file()


def test_stitch() -> None:
    if not shutil.which("ffmpeg"):
        return
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        renders = root_path / "renders"
        (renders / "ma").mkdir(parents=True)
        (renders / "mb").mkdir(parents=True)
        vocals = root_path / "vocals.wav"
        subprocess.run([shutil.which("ffmpeg"), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", str(vocals)], capture_output=True, check=True)
        subprocess.run([shutil.which("ffmpeg"), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", str(renders / "ma" / "full.wav")], capture_output=True, check=True)
        subprocess.run([shutil.which("ffmpeg"), "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", str(renders / "mb" / "full.wav")], capture_output=True, check=True)

        full = {"ma": str(renders / "ma" / "full.wav"), "mb": str(renders / "mb" / "full.wav")}

        solo_segments = [
            {"id": "s1", "start": 0, "end": 1, "assigned_model_ids": ["ma"], "mode": "solo"},
            {"id": "s2", "start": 1, "end": 2, "assigned_model_ids": ["mb"], "mode": "solo"},
        ]
        out = root_path / "merged.wav"
        StitchService().stitch(solo_segments, full, str(vocals), str(out), str(root_path / "log.txt"))
        assert out.is_file()
        probe = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)], capture_output=True, text=True, check=True)
        assert 1.9 <= float(probe.stdout.strip()) <= 2.1

        choir_segments = [
            {"id": "s1", "start": 0, "end": 2, "assigned_model_ids": ["ma", "mb"], "mode": "choir"},
        ]
        choir_out = root_path / "choir.wav"
        StitchService().stitch(choir_segments, full, str(vocals), str(choir_out), str(root_path / "log2.txt"))
        assert choir_out.is_file()
        choir_probe = subprocess.run([shutil.which("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(choir_out)], capture_output=True, text=True, check=True)
        assert 1.9 <= float(choir_probe.stdout.strip()) <= 2.1


def _service_multi3(tmp: Path, ok: bool) -> tuple[WorkService, str]:
    tmp.mkdir(parents=True)
    for n in ("a", "b", "c"):
        (tmp / f"model_{n}.pth").write_bytes(b"model")
    vocal_file = tmp / "vocals.wav"
    vocal_file.write_bytes(b"audio")
    model_repo = ListRepository(tmp / "models.json")
    work_repo = ListRepository(tmp / "works.json")
    for n, mid in (("a", "ma"), ("b", "mb"), ("c", "mc")):
        model_repo.add({"id": mid, "framework": "rvc", "files": {"checkpoint": str(tmp / f"model_{n}.pth")}})
    work = {
        "id": "w1",
        "model_id": "ma",
        "models": [
            {"model_id": "ma", "params": {}},
            {"model_id": "mb", "params": {}},
        ],
        "params": {},
        "segments": [
            {"id": "seg_001", "start": 0, "end": 1, "assigned_model_ids": ["ma"], "mode": "solo"},
            {"id": "seg_002", "start": 1, "end": 2, "assigned_model_ids": ["mc"], "mode": "solo"},
        ],
        "input_mode": "vocals",
        "input_files": [{"role": "vocals", "stored_path": str(vocal_file)}],
        "status": "pending",
        "stage": "prepared",
        "progress": 10,
        "steps": [],
        "logs": [],
        "work_dir": str(tmp / "work_w1"),
        "log_path": str(tmp / "work_w1" / "run.log"),
    }
    work_repo.add(work)
    return WorkService(work_repo, StemPreparer(tmp / "works", shutil.which("ffmpeg") or ""), model_repo, None, FakeRunner(ok)), "w1"


def test_rerender() -> None:
    if not shutil.which("ffmpeg"):
        return
    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service_multi(Path(root) / "r", True)
        service.start_work(work_id)
        work = wait_for(service, work_id, "done")
        assert Path(work["output_files"]["final"]).is_file()
        result = service.rerender_work(work_id)
        assert result["ok"], result
        assert Path(result["work"]["output_files"]["final"]).is_file()


def test_rerender_infers_missing() -> None:
    if not shutil.which("ffmpeg"):
        return
    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service_multi3(Path(root) / "r3", True)
        service.start_work(work_id)
        work = wait_for(service, work_id, "done")
        # mc 未在首次渲染中产出，rerender 应自动补推理 mc 再拼接
        result = service.rerender_work(work_id)
        assert result["ok"], result
        assert Path(result["work"]["output_files"]["final"]).is_file()
        assert (Path(work["work_dir"]) / "renders" / "mc" / "full.wav").is_file()


def test_update_segments() -> None:
    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service_multi(Path(root) / "m", True)
        bad = service.update_work_segments(work_id, {"not": "a list"})
        assert not bad["ok"]
        segs = [
            {"id": "s1", "start": 0, "end": 2, "assigned_model_ids": ["ma"], "mode": "solo"},
        ]
        ok = service.update_work_segments(work_id, segs)
        assert ok["ok"]
        assert ok["work"]["segments"][0]["id"] == "s1"
        assert ok["work"]["segments"][0]["end"] == 2


def test_pitch() -> None:
    if not shutil.which("ffmpeg"):
        return
    from infrastructure.pitch_analyzer import PitchAnalyzer, align_lyrics

    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        tone = root_path / "tone.wav"
        subprocess.run([shutil.which("ffmpeg"), "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(tone)], capture_output=True, check=True)
        result = PitchAnalyzer().analyze(str(tone))
        assert result["ok"], result
        assert result["notes"]
        midis = [note["midi"] for note in result["notes"]]
        assert any(68 <= midi <= 70 for midi in midis), midis

        aligned = align_lyrics(["line one", "line two"], result["notes"])
        assert len(aligned) == 2
        assert aligned[0]["text"] == "line one"


class _FakeEngine:
    framework: str

    def __init__(self, framework: str, ok: bool) -> None:
        self.framework = framework
        self._ok = ok

    def available(self) -> bool:
        return True

    def infer(self, model, vocals_path, out_path, params, log_path):
        if not self._ok:
            return {"ok": False, "error": "boom"}
        Path(out_path).write_bytes(b"x")
        return {"ok": True, "path": out_path}


def test_registry() -> None:
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        registry = EngineRegistry([_FakeEngine("rvc", True), _FakeEngine("so-vits-svc", True)])
        runner = InferenceRunner(None, registry)
        work = {"work_dir": str(root_path / "w"), "log_path": str(root_path / "w" / "run.log")}

        ok = runner.run_rvc(work, {"framework": "so-vits-svc"}, "v.wav")
        assert ok["ok"] and Path(ok["path"]).is_file()

        bad = runner.run_rvc(work, {"framework": "unknown"}, "v.wav")
        assert not bad["ok"]

        registry_fail = EngineRegistry([_FakeEngine("rvc", False)])
        runner_fail = InferenceRunner(None, registry_fail)
        failed = runner_fail.run_rvc(work, {"framework": "rvc"}, "v.wav")
        assert not failed["ok"]


if __name__ == "__main__":
    smoke()
    test_stitch()
    test_rerender()
    test_update_segments()
    test_pitch()
    test_registry()
