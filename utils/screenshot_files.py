"""Publish complete screenshots without ever replacing an existing filename."""
import itertools
import logging
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import BinaryIO, Callable
from utils.capture_diagnostics import timed

logger = logging.getLogger(__name__)


def write_screenshot(directory: Path, writer: Callable[[BinaryIO], None]) -> Path:
    """Stage in the destination filesystem, then atomically link to a free name.

    The exclusive link operation handles collisions from other processes, files,
    directories and symlinks. Never use exists()+write or a replacing rename.
    Filesystems without hard-link support fail cleanly rather than overwrite.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y-%m-%d_%H-%M-%S')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w+b', dir=directory,
                                         prefix='.capture-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            writer(stream)
            stream.flush()
        for counter in itertools.count():
            suffix = '' if counter == 0 else f'_{counter:03d}'
            destination = directory / f'Screenshot_{stamp}{suffix}.png'
            try:
                os.link(temporary, destination)
            except FileExistsError:
                continue
            return destination
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError as error:
                logger.warning('Could not remove screenshot staging file: %s', type(error).__name__)


def copy_screenshot(source: Path, directory: Path) -> Path:
    """Copy encoded bytes unchanged, keeping the source intact."""
    def write(stream):
        with Path(source).open('rb') as original:
            shutil.copyfileobj(original, stream)
    return write_screenshot(directory, write)


@timed('png_encode_publish')
def save_png(image, directory: Path) -> Path:
    """Keep the existing Pillow PNG encoding, with safe publication."""
    return write_screenshot(directory, lambda stream: image.save(stream, 'PNG'))


def cleanup_capture_source(source: Path | None, screenshot_directory: Path) -> None:
    """Clean a portal temporary without deleting anything in saved screenshots."""
    if source is None:
        return
    source = Path(source)
    try:
        directory = Path(screenshot_directory)
        if (Path(os.path.abspath(source)).is_relative_to(Path(os.path.abspath(directory)))
                or source.resolve().is_relative_to(directory.resolve())):
            return
        source.unlink(missing_ok=True)
    except OSError:
        pass
