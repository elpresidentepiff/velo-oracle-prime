"""
PDF Parser Adapter Layer — source-truth loop candidate harness
===============================================================
Uniform interface over PDF parsers so the benchmark (and later the
source-truth loop) can compare them like-for-like. NO scoring
integration — adapters return parsed artifacts only.

Adapters:
  CurrentParserAdapter — pdfplumber (what ingestion_spine-era parsing uses)
  LiteParseAdapter     — run-llama/liteparse (local, OCR-capable, bboxes)
  NullParserAdapter    — control: always returns empty (harness sanity)

Schema (every adapter, identical keys):
  parser_name, parser_version, source_file, file_sha256, page_count,
  text, json_blocks, screenshots, warnings, runtime_sec
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _base(parser_name: str, version: str, path: Path) -> dict:
    return {
        "parser_name": parser_name,
        "parser_version": version,
        "source_file": str(path),
        "file_sha256": _sha256(path),
        "page_count": 0,
        "text": "",
        "json_blocks": [],
        "screenshots": [],
        "warnings": [],
        "runtime_sec": 0.0,
    }


class CurrentParserAdapter:
    name = "pdfplumber_current"

    def parse(self, path: Path) -> dict:
        import pdfplumber

        out = _base(self.name, pdfplumber.__version__, path)
        t0 = time.perf_counter()
        try:
            with pdfplumber.open(path) as pdf:
                out["page_count"] = len(pdf.pages)
                texts = []
                for page in pdf.pages:
                    texts.append(page.extract_text() or "")
                out["text"] = "\n".join(texts)
        except Exception as e:
            out["warnings"].append(f"parse_failed: {e}")
        out["runtime_sec"] = round(time.perf_counter() - t0, 3)
        return out


class LiteParseAdapter:
    name = "liteparse"

    def parse(self, path: Path, ocr: bool = True) -> dict:
        try:
            import liteparse
            version = getattr(liteparse, "__version__", "2.x")
        except ImportError:
            version = "cli"
        out = _base(self.name, version, path)
        t0 = time.perf_counter()
        lit = str(ROOT / "venv" / "bin" / "lit")
        with tempfile.TemporaryDirectory() as td:
            jout = Path(td) / "out.json"
            cmd = [lit, "parse", str(path), "--format", "json", "-o", str(jout)]
            if not ocr:
                cmd.append("--no-ocr")
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if proc.returncode != 0:
                    out["warnings"].append(f"lit_exit_{proc.returncode}: {proc.stderr[:200]}")
                elif jout.exists():
                    doc = json.loads(jout.read_text())
                    pages = doc.get("pages", doc if isinstance(doc, list) else [])
                    out["page_count"] = len(pages)
                    out["json_blocks"] = pages
                    out["text"] = "\n".join(
                        (p.get("text") or "") if isinstance(p, dict) else str(p) for p in pages
                    ) or doc.get("text", "") if isinstance(doc, dict) else out["text"]
                    if isinstance(doc, dict) and not out["text"]:
                        out["text"] = doc.get("text", "")
            except subprocess.TimeoutExpired:
                out["warnings"].append("lit_timeout_300s")
            except Exception as e:
                out["warnings"].append(f"lit_failed: {e}")
        out["runtime_sec"] = round(time.perf_counter() - t0, 3)
        return out


class NullParserAdapter:
    name = "null_control"

    def parse(self, path: Path) -> dict:
        return _base(self.name, "0", path)


ADAPTERS = {
    "current": CurrentParserAdapter,
    "liteparse": LiteParseAdapter,
    "null": NullParserAdapter,
}
