"""Helpers for converting official Charles native sessions into XML."""

from __future__ import annotations

import subprocess
from pathlib import Path


class NativeSessionConversionError(RuntimeError):
    """Raised when Charles CLI conversion fails."""


def convert_native_session_to_xml(
    *,
    charles_cli_path: str,
    source_path: str | Path,
    target_path: str | Path,
) -> Path:
    """Run `charles convert <infile> <outfile>` and return the XML target path."""
    source = Path(source_path)
    target = Path(target_path)
    command = [charles_cli_path, "convert", str(source), str(target)]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        raise NativeSessionConversionError(
            f"Charles convert failed ({result.returncode}): {stderr or 'no error output'}"
        )
    if not target.exists():
        raise NativeSessionConversionError(
            f"Charles convert did not create the expected output: {target}"
        )
    return target
