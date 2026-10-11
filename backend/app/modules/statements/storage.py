"""Statement file storage.

Files are stored under a UUID name so the original filename can never be
used for path traversal. The SHA-256 of the content is computed at upload
time for duplicate detection.
"""

import hashlib
import uuid
from pathlib import Path

from app.core.config import settings


class StatementStorage:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.uploads_path) / "statements"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, filename: str, content: bytes) -> tuple[str, str, str]:
        """Persist content under a UUID name.

        Returns ``(stored_filename, sha256_hex, extension_without_dot)``.
        """
        digest = hashlib.sha256(content).hexdigest()
        extension = Path(filename).suffix.lower().lstrip(".")
        stored = f"{uuid.uuid4().hex}.{extension}" if extension else uuid.uuid4().hex
        (self.base_dir / stored).write_bytes(content)
        return stored, digest, extension

    @staticmethod
    def hash_content(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def path_for(self, stored_filename: str) -> Path:
        """Resolve a stored filename to an absolute path (traversal-safe)."""
        if Path(stored_filename).name != stored_filename:
            raise ValueError("Invalid stored filename.")
        return self.base_dir / stored_filename

    def read(self, stored_filename: str) -> bytes:
        """Read a stored file's bytes."""
        return self.path_for(stored_filename).read_bytes()

    def delete(self, stored_filename: str) -> None:
        """Best-effort cleanup for a staged file whose database write failed."""
        self.path_for(stored_filename).unlink(missing_ok=True)
