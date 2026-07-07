from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from application.stem_preparer import StemPreparer


def smoke() -> None:
    with tempfile.TemporaryDirectory() as root:
        src = Path(root) / "vocal.mp3"
        src.write_bytes(b"audio")
        result = StemPreparer(Path(root) / "works", "/bin/ffmpeg").prepare({"mode": "vocals", "vocals_path": str(src)})
        assert result["ok"]
        assert result["files"]["vocals"].endswith("vocals.mp3")

    with tempfile.TemporaryDirectory() as root:
        src = Path(root) / "vocal.mp3"
        src.write_bytes(b"audio")
        with patch("application.stem_preparer.subprocess.run") as run:
            result = StemPreparer(Path(root) / "works", "/bin/ffmpeg").prepare({"mode": "vocals", "vocals_path": str(src), "normalize_input": True})
        assert result["ok"]
        assert result["files"]["vocals"].endswith("vocals.wav")
        run.assert_called_once()


if __name__ == "__main__":
    smoke()
