"""Execution helpers for compound report sections."""

import json
import subprocess
import sys


def _parse_json_payload(text: str):
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def run_section(command: list[str], cwd: str):
    """Run a section command in JSON mode and capture result metadata."""
    proc = subprocess.run(
        [sys.executable, "-m", "roam", "--json", *command],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    payload = _parse_json_payload(proc.stdout)
    ok = proc.returncode == 0 and payload is not None
    return {
        "ok": ok,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "payload": payload,
    }
