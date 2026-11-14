"""Run existing OCR outside the GUI; cancellation terminates Tesseract children."""
import asyncio
import json
import os
from pathlib import Path
import signal
import sys


async def extract_text_async(path):
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'utils.ocr_job', str(path),
        cwd=Path(__file__).resolve().parents[1],
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True)
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=180)
        result = json.loads(output)
        if process.returncode or 'error' in result:
            raise RuntimeError(result.get('error', 'Local OCR failed.'))
        return result['text']
    finally:
        # The process group includes any running Tesseract subprocess.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
