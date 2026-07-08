from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from application.model_service import ModelService
from infrastructure.storage import ListRepository


def test_import_model_from_url() -> None:
    with tempfile.TemporaryDirectory() as root:
        root_path = Path(root)
        models_dir = root_path / "models"
        repo = ListRepository(root_path / "models.json")

        archive = root_path / "model.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("G_123.pth", b"checkpoint")
            zf.writestr("config.json", '{"model": {}}')
            zf.writestr("model_123.index", b"index")

        service = ModelService(repo, models_dir)
        result = service.import_model_from_url({"url": archive.as_uri(), "name": "remote"})
        assert result["ok"], result
        model = result["model"]
        assert model["framework"] == "so-vits-svc"
        assert model["files"].get("checkpoint", "").endswith("checkpoint.pth")
        assert model["files"].get("config", "").endswith("config.json")
        assert model["files"].get("index", "").endswith("index.index")
        # default model was first
        assert model["is_default"] is True


if __name__ == "__main__":
    test_import_model_from_url()
    print("OK")
