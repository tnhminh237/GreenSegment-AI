"""Reuse the final Gemini advisor without changing existing src/gemini_advisor.py."""
from __future__ import annotations

import argparse
import importlib.util
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ADVISOR_PATH = ROOT / "src" / "gemini_advisor.py"


@lru_cache(maxsize=1)
def _advisor():
    if not ADVISOR_PATH.is_file():
        raise FileNotFoundError(f"Thiếu file {ADVISOR_PATH.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location("greensegment_gemini_advisor", ADVISOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Không thể tải src/gemini_advisor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _context(payload: dict[str, Any]):
    mode = payload["mode"]
    args = argparse.Namespace(
        mode=mode,
        city=None,
        city_id=str(payload.get("city_id", "")) if mode == "city" else None,
        country=None,
        cluster=int(payload["cluster_id"]) if mode == "cluster" else None,
    )
    return _advisor().prepare_context(args)


def preview(payload: dict[str, Any]) -> dict[str, Any]:
    context, shortlist = _context(payload)
    return {"input": context["subject"], "catalog_solutions": shortlist,
            "note": "Chưa gọi API Gemini; đây là dữ liệu đầu vào và ứng viên giải pháp."}


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    module = _advisor()
    context, shortlist = _context(payload)
    model = payload.get("model") or module.DEFAULT_MODEL
    raw = module.call_gemini(context, model, retries=2)
    verified = module.verify_recommendations(raw, shortlist, context)
    return {"input": context["subject"], "model": model, "advisor": verified}
