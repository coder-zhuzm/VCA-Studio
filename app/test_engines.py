"""Engine command construction and stitch timeline tests.

These are the tests that would have caught the "CLI surface doesn't exist"
class of bug: they snapshot the exact argv each engine builds, and verify the
stitcher places segments on the absolute timeline (leading/gap/tail silence).
Run directly: `python test_engines.py`.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch

from application.stitch_service import StitchService
from infrastructure.rvc_engine import RvcEngine, resolve_device
from infrastructure.svc_engine import SvcEngine


class FakeSettings:
    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, key: str, default=None):
        return self._data.get(key, default)


def test_rvc_command() -> None:
    settings = FakeSettings({"rvc_python": "/venv/bin/python"})
    engine = RvcEngine(settings)
    model = {"files": {"checkpoint": "/m/model.pth", "index": "/m/model.index"}}
    params = {"f0_method": "rmvpe", "transpose": 2, "index_rate": 0.6, "protect": 0.4, "filter_radius": 5, "rms_mix_rate": 0.8, "device": "cuda"}
    cmd = engine._command(model, "/in/v.wav", "/out/o.wav", params)
    assert cmd[1:4] == ["-m", "rvc_python", "cli"], cmd
    text = " ".join(cmd)
    assert "-i /in/v.wav" in text
    assert "-o /out/o.wav" in text
    assert "-mp /m/model.pth" in text
    assert "-me rmvpe" in text
    assert "-pi 2" in text
    assert "-ir 0.6" in text
    assert "-pr 0.4" in text
    assert "-fr 5" in text
    assert "-rmr 0.8" in text
    assert "-de cuda:0" in text  # cuda 归一化为 cuda:0
    assert "-ip /m/model.index" in text
    # 无 index 时不带 -ip
    cmd2 = engine._command({"files": {"checkpoint": "/m/model.pth"}}, "/i.wav", "/o.wav", {})
    assert "-ip" not in cmd2
    # 旧接口的参数名不应再出现
    assert not any(a.startswith("--input_path") or a == "infer_file" for a in cmd)
    print("test_rvc_command OK")


def test_resolve_device() -> None:
    assert resolve_device("cpu") == "cpu"
    assert resolve_device("mps") == "mps"
    assert resolve_device("cuda") == "cuda:0"
    with patch("application.host_probe.probe_host", return_value={"recommended_device": "mps"}):
        assert resolve_device("auto") == "mps"
    print("test_resolve_device OK")


def test_svc_command() -> None:
    settings = FakeSettings({"svc_python": "/svc/bin/python", "sovits_repo": "/repo"})
    engine = SvcEngine(settings)
    files = {"checkpoint": "/m/G.pth", "config": "/m/config.json", "diffusion": "/m/diff.pt"}
    params = {"transpose": -1, "f0_predictor": "harvest", "speaker": "singer_a", "shallow_diffusion": True, "device": "cpu"}
    cmd = engine._command(files, files["checkpoint"], files["config"], "/in/v.wav", "/out/o.wav", params)
    text = " ".join(cmd)
    assert cmd[1].endswith("svc_worker.py"), cmd
    assert "--model /m/G.pth" in text
    assert "--config /m/config.json" in text
    assert "--input /in/v.wav" in text
    assert "--output /out/o.wav" in text
    assert "--transpose -1" in text
    assert "--f0_predictor harvest" in text
    assert "--speaker singer_a" in text
    assert "--shallow_diffusion" in text
    assert "--diffusion_model /m/diff.pt" in text
    assert "--device cpu" in text
    # speaker 留空则不传，交给 worker 从 config 取第一个
    cmd2 = engine._command(files, files["checkpoint"], files["config"], "/i.wav", "/o.wav", {})
    assert "--speaker" not in cmd2
    print("test_svc_command OK")


def _tone(path: Path, dur: float, freq: int = 440) -> None:
    ffmpeg = shutil.which("ffmpeg")
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=44100", "-t", str(dur), "-ac", "2", str(path)],
        capture_output=True,
        check=True,
    )


def _duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def test_stitch_timeline() -> None:
    """首段前与段间 gap 需填静音，尾部补齐到人声总长。"""
    if not shutil.which("ffmpeg"):
        print("test_stitch_timeline SKIP (no ffmpeg)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vocals = root / "vocals.wav"
        render = root / "full.wav"
        _tone(vocals, 10.0)
        _tone(render, 10.0, freq=880)
        segments = [
            {"id": "s1", "start": 2.0, "end": 4.0, "assigned_model_ids": ["m1"], "mode": "solo", "fade_in": 0.01, "fade_out": 0.01},
            {"id": "s2", "start": 6.0, "end": 8.0, "assigned_model_ids": ["m1"], "mode": "solo", "fade_in": 0.01, "fade_out": 0.01},
        ]
        out = root / "merged.wav"
        service = StitchService(shutil.which("ffmpeg") or "")
        service.stitch(segments, {"m1": str(render)}, str(vocals), str(out), str(root / "run.log"))
        assert out.is_file()
        # 输出应对齐到人声总长（2s 前导 + 2s 段 + 2s gap + 2s 段 + 2s 尾部）
        dur = _duration(out)
        assert abs(dur - 10.0) < 0.1, f"expected ~10s, got {dur}"
    print("test_stitch_timeline OK")


def test_stitch_mixed_rates() -> None:
    """不同采样率片段拼接不应损坏（统一格式后 concat）。"""
    if not shutil.which("ffmpeg"):
        print("test_stitch_mixed_rates SKIP (no ffmpeg)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        vocals = root / "vocals.wav"
        render = root / "full.wav"
        _tone(vocals, 6.0)
        # 模型渲染是 48k 单声道，与 44.1k 立体声人声不一致
        ffmpeg = shutil.which("ffmpeg")
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000", "-t", "6", "-ac", "1", str(render)],
            capture_output=True,
            check=True,
        )
        segments = [
            {"id": "s1", "start": 1.0, "end": 3.0, "assigned_model_ids": ["m1"], "mode": "solo", "fade_in": 0, "fade_out": 0},
            {"id": "s2", "start": 3.0, "end": 5.0, "mode": "original", "assigned_model_ids": ["orig"], "fade_in": 0, "fade_out": 0},
        ]
        out = root / "merged.wav"
        service = StitchService(ffmpeg or "")
        service.stitch(segments, {"m1": str(render)}, str(vocals), str(out), str(root / "run.log"))
        with wave.open(str(out), "rb") as w:
            assert w.getframerate() == 44100
            assert w.getnchannels() == 2
        assert abs(_duration(out) - 6.0) < 0.1
    print("test_stitch_mixed_rates OK")




def test_cancel_work() -> None:
    """pending 作品可直接取消；cancelled 可重试回 pending。"""
    import tempfile as _tf

    from application.stem_preparer import StemPreparer
    from application.work_service import WorkService
    from infrastructure.storage import ListRepository

    with _tf.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src = root / "v.wav"
        _tone(src, 1.0) if shutil.which("ffmpeg") else src.write_bytes(b"RIFF0000WAVE")
        work_repo = ListRepository(root / "works.json")
        model_repo = ListRepository(root / "models.json")
        model_repo.add({"id": "m1", "framework": "rvc", "files": {"checkpoint": str(src)}})
        service = WorkService(work_repo, StemPreparer(root / "works", shutil.which("ffmpeg") or ""), model_repo, None, None)
        created = service.create_work({"mode": "vocals", "vocals_path": str(src), "model_id": "m1"})
        assert created["ok"], created
        wid = created["work"]["id"]
        cancelled = service.cancel_work(wid)
        assert cancelled["work"]["status"] == "cancelled", cancelled
        retried = service.retry_work(wid)
        assert retried["work"]["status"] == "pending", retried
        # 幂等：对已完成状态取消不报错
        again = service.cancel_work(wid)
        assert again["ok"]
    print("test_cancel_work OK")


if __name__ == "__main__":
    test_rvc_command()
    test_resolve_device()
    test_svc_command()
    test_stitch_timeline()
    test_stitch_mixed_rates()
    test_cancel_work()
