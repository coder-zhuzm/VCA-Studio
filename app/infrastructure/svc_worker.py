"""So-VITS-SVC inference worker, executed under the configured `svc_python`.

Runs inside the configured So-VITS-SVC repository (cwd / sys.path) and drives
`inference.infer_tool.Svc` directly instead of guessing a CLI surface — the CLI
entry (`inference_main.py`) and its flags vary across forks, but the `Svc`
class constructor + `slice_inference` API is stable in 4.0/4.1 lineages.
Unknown constructor / inference kwargs are filtered via `inspect` so the worker
degrades gracefully on older forks.

Protocol: prints a single line `SVC_RESULT {json}` to stdout.
Also supports `--check` to validate the environment without inferring.
"""

from __future__ import annotations

import argparse
import inspect
import json
import sys
from pathlib import Path


def _filter_kwargs(func, kwargs: dict) -> dict:
    try:
        accepted = set(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return {}
    return {k: v for k, v in kwargs.items() if k in accepted}


def _check(repo: str) -> dict:
    checks = []
    for module in ("torch", "librosa", "soundfile"):
        try:
            __import__(module)
            checks.append({"module": module, "ok": True})
        except Exception as exc:  # noqa: BLE001
            checks.append({"module": module, "ok": False, "error": str(exc)})
    sys.path.insert(0, repo)
    try:
        from inference import infer_tool  # noqa: F401

        checks.append({"module": "inference.infer_tool", "ok": True})
    except Exception as exc:  # noqa: BLE001
        checks.append({"module": "inference.infer_tool", "ok": False, "error": str(exc)})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _infer(args: argparse.Namespace) -> dict:
    sys.path.insert(0, args.repo)
    import soundfile
    from inference.infer_tool import Svc

    ctor_kwargs = _filter_kwargs(
        Svc.__init__,
        {
            "net_g_path": args.model,
            "config_path": args.config,
            "device": args.device or None,
            "cluster_model_path": args.cluster_model or "",
            "shallow_diffusion": bool(args.shallow_diffusion),
            "diffusion_model_path": args.diffusion_model or "",
            "diffusion_config_path": args.diffusion_config or "",
            "feature_retrieval": False,
        },
    )
    # net_g_path / config_path are positional in every known fork.
    ctor_kwargs.pop("net_g_path", None)
    ctor_kwargs.pop("config_path", None)
    model = Svc(args.model, args.config, **ctor_kwargs)

    speaker = args.speaker
    if not speaker:
        spk = (model.hps_ms.spk if hasattr(model, "hps_ms") else None) or {}
        keys = list(spk.keys()) if hasattr(spk, "keys") else []
        if not keys:
            raise RuntimeError("config.json 中没有 spk 说话人，且未指定 speaker。")
        speaker = keys[0]

    infer_kwargs = _filter_kwargs(
        model.slice_inference,
        {
            "raw_audio_path": args.input,
            "spk": speaker,
            "tran": int(args.transpose),
            "slice_db": -40,
            "cluster_infer_ratio": float(args.cluster_ratio),
            "auto_predict_f0": False,
            "noice_scale": 0.4,
            "noise_scale": 0.4,  # some forks fixed the typo
            "pad_seconds": 0.5,
            "clip_seconds": 0,
            "lg_num": 0,
            "lgr_num": 0.75,
            "f0_predictor": args.f0_predictor,
            "enhancer_adaptive_key": 0,
            "cr_threshold": 0.05,
            "k_step": 100,
            "use_spk_mix": False,
            "second_encoding": False,
            "loudness_envelope_adjustment": 1,
        },
    )
    audio = model.slice_inference(**infer_kwargs)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    soundfile.write(str(out), audio, model.target_sample)
    return {"ok": True, "path": str(out), "speaker": speaker}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--config", default="")
    parser.add_argument("--input", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--speaker", default="")
    parser.add_argument("--transpose", default="0")
    parser.add_argument("--f0_predictor", default="rmvpe")
    parser.add_argument("--cluster_ratio", default="0")
    parser.add_argument("--cluster_model", default="")
    parser.add_argument("--device", default="")
    parser.add_argument("--shallow_diffusion", action="store_true")
    parser.add_argument("--diffusion_model", default="")
    parser.add_argument("--diffusion_config", default="")
    args = parser.parse_args()

    try:
        result = _check(args.repo) if args.check else _infer(args)
    except Exception as exc:  # noqa: BLE001 - report any failure back to the host
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print("SVC_RESULT " + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
