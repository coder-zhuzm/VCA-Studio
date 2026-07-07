from __future__ import annotations

import tempfile
from pathlib import Path
from time import monotonic
from unittest.mock import patch

from application.stem_preparer import StemPreparer
from application.work_service import WorkService
from infrastructure.storage import ListRepository


class FakeRunner:
    def __init__(self, ok: bool) -> None:
        self.ok = ok

    def run_rvc(self, work, model, vocals_path):
        if not self.ok:
            return {"ok": False, "error": "boom"}
        out = Path(work["work_dir"]) / "inference" / "ai_vocal.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(Path(vocals_path).read_bytes())
        return {"ok": True, "path": str(out)}


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
    return WorkService(work_repo, StemPreparer(tmp / "works", "/bin/ffmpeg" if stems else ""), model_repo, None, FakeRunner(ok)), "w1"


def wait_for(service: WorkService, work_id: str, status: str):
    deadline = monotonic() + 2
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
        run.assert_called_once()

    with tempfile.TemporaryDirectory() as root:
        service, work_id = _service(Path(root) / "fail", False)
        work = service.start_work(work_id)["work"]
        assert work["status"] == "running"
        work = wait_for(service, work_id, "failed")
        assert work["stage"] == "failed"
        assert work["logs"][-1]["message"] == "boom"
        assert [step["status"] for step in work["steps"] if step["key"] == "run"] == ["failed"]


if __name__ == "__main__":
    smoke()
