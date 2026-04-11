from supabase import create_client

from app.config import settings

_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


async def upload_file(
    bucket: str, path: str, content: bytes, content_type: str = "application/octet-stream"
) -> str:
    _client.storage.from_(bucket).upload(
        path, content, file_options={"content-type": content_type, "upsert": "true"}
    )
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"


async def download_file(bucket: str, path: str) -> bytes:
    return _client.storage.from_(bucket).download(path)


async def delete_file(bucket: str, path: str) -> None:
    _client.storage.from_(bucket).remove([path])


async def list_files(bucket: str, prefix: str = "") -> list[str]:
    return [
        f["name"]
        for f in _client.storage.from_(bucket).list(prefix)
        if f.get("name")
    ]


async def signed_url(bucket: str, path: str, expires_in: int = 3600) -> str:
    return _client.storage.from_(bucket).create_signed_url(path, expires_in)["signedURL"]
