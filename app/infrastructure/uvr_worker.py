"""UVR separation worker executed under the configured UVR Python interpreter.

Uses the `audio_separator` package to split a full song into vocals / instrumental
and optionally apply de-reverb / de-echo on the vocals. Output is copied to the
canonical paths requested by the caller so the rest of the pipeline stays stable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path


def _classify_stems(outputs: list[str]) -> tuple[str | None, str | None]:
    vocals = next((p for p in outputs if "inst" not in Path(p).stem.lower()), None)
    instrumental = next((p for p in outputs if "inst" in Path(p).stem.lower()), None)
    return vocals, instrumental


def _run_separation(input_path: str, model_dir: str, model_filename: str, work_dir: str) -> list[str]:
    from audio_separator.separator import Separator

    separator = Separator(model_file_dir=model_dir, output_dir=work_dir)
    separator.load_model(model_filename=model_filename)
    return separator.separate(input_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--model_dir", required=True)
    parser.add_argument("--separator_model", default="5_HP-Karaoke-UVR.pth")
    parser.add_argument("--dereverb_model", default="UVR-DeEcho-DeReverb.pth")
    parser.add_argument("--do_dereverb", action="store_true")
    parser.add_argument("--vocals_out", required=True)
    parser.add_argument("--instrumental_out", required=True)
    args = parser.parse_args()

    result: dict[str, object] = {"ok": False, "error": ""}
    try:
        model_dir = str(Path(args.model_dir).expanduser())
        with tempfile.TemporaryDirectory() as work_dir:
            outputs = _run_separation(args.input, model_dir, args.separator_model, work_dir)
            vocals, instrumental = _classify_stems(outputs)
            if not vocals:
                raise RuntimeError("分离未产生人声输出。")

            if args.do_dereverb:
                dereverbed = _run_separation(vocals, model_dir, args.dereverb_model, work_dir)
                if dereverbed:
                    vocals = dereverbed[0]

            vocals_out = Path(args.vocals_out)
            instrumental_out = Path(args.instrumental_out)
            vocals_out.parent.mkdir(parents=True, exist_ok=True)
            instrumental_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(vocals, vocals_out)
            if instrumental:
                shutil.copy2(instrumental, instrumental_out)

            result = {
                "ok": True,
                "vocals": str(vocals_out),
                "instrumental": str(instrumental_out) if instrumental else "",
            }
    except Exception as exc:  # noqa: BLE001 - report any failure back to the host
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    print("UVR_RESULT " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
