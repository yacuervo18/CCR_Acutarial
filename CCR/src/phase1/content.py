"""Lectura controlada de contenidos informativos por proceso."""
from dataclasses import dataclass
import os
from pathlib import Path


CONTENT_ROOT = Path(__file__).resolve().parents[2] / "content"
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov"}
MAX_VIDEO_SIZE_BYTES = 200 * 1024 * 1024


@dataclass(frozen=True)
class ProcessContent:
    what_to_do: str
    manual_url: str | None
    important_note: str
    video_path: Path | None


def _process_media_dir(code: str) -> Path:
    """Returns a process media directory constrained to the content root."""
    process_root = (CONTENT_ROOT / code).resolve()
    content_root = CONTENT_ROOT.resolve()
    if process_root.parent != content_root:
        raise ValueError("Código de proceso inválido.")
    media_dir = process_root / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    return media_dir


def video_paths(code: str) -> list[Path]:
    media_dir = _process_media_dir(code)
    return sorted(
        path
        for path in media_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
    )


def save_uploaded_video(code: str, uploaded_file, max_size: int = MAX_VIDEO_SIZE_BYTES) -> Path:
    """Atomically stores one uploaded video and removes previous video variants."""
    filename = Path(uploaded_file.name or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_SUFFIXES:
        raise ValueError("El video debe estar en formato MP4, WebM o MOV.")
    data = uploaded_file.getbuffer()
    if not data:
        raise ValueError("El archivo de video está vacío.")
    if len(data) > max_size:
        raise ValueError("El video supera el tamaño máximo permitido de 200 MB.")

    media_dir = _process_media_dir(code)
    target = media_dir / f"video{suffix}"
    temporary = media_dir / f".{target.name}.tmp"
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
        for path in video_paths(code):
            if path != target:
                path.unlink()
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def delete_videos(code: str) -> None:
    """Deletes only supported video files belonging to the process."""
    for path in video_paths(code):
        path.unlink()


def load_process_content(
    code: str,
    fallback_description: str,
    stored_content: dict[str, str] | None = None,
) -> ProcessContent:
    """Carga contenido opcional sin afectar la configuración ni el estado del proceso."""
    process_root = CONTENT_ROOT / code
    description_path = process_root / "que_hay_que_hacer.txt"
    manual_path = process_root / "manual_url.txt"
    important_path = process_root / "importante.txt"

    what_to_do = fallback_description
    if description_path.is_file():
        text = description_path.read_text(encoding="utf-8").strip()
        if text:
            what_to_do = text

    manual_url = None
    if manual_path.is_file():
        value = manual_path.read_text(encoding="utf-8").strip()
        if value:
            manual_url = value

    important_note = ""
    if important_path.is_file():
        important_note = important_path.read_text(encoding="utf-8").strip()

    if stored_content:
        what_to_do = stored_content.get("what_to_do") or what_to_do
        manual_url = stored_content.get("manual_url") or None
        important_note = stored_content.get("important_note") or important_note

    video_path = next(iter(video_paths(code)), None)
    return ProcessContent(what_to_do, manual_url, important_note, video_path)
