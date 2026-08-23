"""Payment-proof object storage.

Production uses a PRIVATE Backblaze B2 bucket via the S3-compatible API
(boto3). Dev/tests use a local-disk backend so no credentials are needed.
Screenshots are never public — admins access proofs only through the
authenticated FastAPI endpoint, which either streams the bytes or returns a
short-lived signed URL.
"""
import shutil
from pathlib import Path
from typing import Any, Protocol

from app.config.settings import settings


class ProofStorageError(RuntimeError):
    pass


class ProofStorage(Protocol):
    supports_signed_urls: bool

    def save(self, key: str, data: bytes, mime_type: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def get_bytes(self, key: str) -> bytes | None: ...

    def signed_url(self, key: str, expires_in: int = 300) -> str | None: ...

    def exists(self, key: str) -> bool: ...


class LocalStorage:
    """Disk-backed storage for development and tests."""

    supports_signed_urls = False

    def __init__(self, root: str):
        self._root = Path(root)

    def _path(self, key: str) -> Path:
        if ".." in key or key.startswith("/"):
            raise ProofStorageError("Invalid proof key")
        return self._root / key

    def save(self, key: str, data: bytes, mime_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def get_bytes(self, key: str) -> bytes | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()


class B2Storage:
    """Private Backblaze B2 bucket via the S3-compatible API."""

    supports_signed_urls = True

    def __init__(self, bucket: str, region: str, access_key_id: str, secret_key: str):
        import boto3
        from botocore.config import Config

        if not all([bucket, region, access_key_id, secret_key]):
            raise ProofStorageError(
                "PROOF_STORAGE_BACKEND=b2 requires B2_BUCKET, B2_REGION, "
                "B2_ACCESS_KEY_ID and B2_SECRET_ACCESS_KEY in .env"
            )
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://s3.{region}.backblazeb2.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )

    def save(self, key: str, data: bytes, mime_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=mime_type
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def get_bytes(self, key: str) -> bytes | None:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
            return obj["Body"].read()
        except self._client.exceptions.NoSuchKey:
            return None

    def signed_url(self, key: str, expires_in: int = 300) -> str | None:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False


_storage: Any = None


def get_proof_storage() -> ProofStorage:
    global _storage
    if _storage is not None:
        return _storage  # type: ignore[return-value]
    backend = settings.PROOF_STORAGE_BACKEND
    if backend == "b2":
        _storage = B2Storage(
            bucket=settings.B2_BUCKET or "",
            region=settings.B2_REGION or "",
            access_key_id=settings.B2_ACCESS_KEY_ID or "",
            secret_key=settings.B2_SECRET_ACCESS_KEY or "",
        )
    elif backend == "local":
        _storage = LocalStorage(settings.PROOF_LOCAL_DIR)
    else:
        raise ProofStorageError(f"Unknown PROOF_STORAGE_BACKEND: {backend!r}")
    return _storage  # type: ignore[return-value]


def reset_proof_storage() -> None:
    """Test helper — force re-construction on next use."""
    global _storage
    _storage = None


def cleanup_local_proofs() -> None:
    """Test helper — wipe the local proof directory between tests."""
    root = Path(settings.PROOF_LOCAL_DIR)
    if root.is_dir():
        shutil.rmtree(root)
