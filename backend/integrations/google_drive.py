"""
Minimal Google Drive wrapper used only by the "grok_drive" AI provider
(see ai/llm_client.py — _call_grok_drive).

Auth model: OAuth as YOUR OWN Google account (not a service account).

Why not a service account: Google gives service accounts zero storage
quota, so they can't create new files even in a folder shared with them —
you'll hit a 403 "Service Accounts do not have storage quota" error every
time. The fix is to authenticate as a real user instead.

This still only requires a ONE-TIME browser consent, not a login on every
request: run `python scripts/get_drive_token.py` once, approve access in
the browser, and it saves a token file that this module reloads and
silently auto-refreshes forever after (until you revoke access).

Use the SAME Google account you connected to Grok's Drive connector at
grok.com/tasks, and point GOOGLE_DRIVE_FOLDER_ID at a folder that already
exists in that account's own Drive — no folder-sharing step needed, since
you own the folder outright.

This module intentionally uses ONE flat folder with prefixed filenames
(rather than nested inbox/outbox subfolders) — it's simpler to set up (one
folder ID) and simpler for Grok's instructions to reference reliably.
"""
import io
import logging
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

_service = None


class DriveError(Exception):
    pass


def _get_service():
    """Lazily builds and caches the Drive API client, refreshing the saved
    OAuth token if its access token has expired."""
    global _service
    if _service is not None:
        return _service

    if not settings.GOOGLE_OAUTH_TOKEN_FILE:
        raise DriveError("GOOGLE_OAUTH_TOKEN_FILE is not set in .env.")
    if not settings.GOOGLE_DRIVE_FOLDER_ID:
        raise DriveError("GOOGLE_DRIVE_FOLDER_ID is not set in .env.")

    token_path = Path(settings.GOOGLE_OAUTH_TOKEN_FILE)
    if not token_path.exists():
        raise DriveError(
            f"No token file found at {token_path}. Run `python scripts/get_drive_token.py` "
            "once from the backend/ directory to authorize Drive access as your Google account."
        )

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _service
    except (OSError, ValueError) as e:
        raise DriveError(f"Could not load or refresh Google OAuth credentials: {e}") from e


def upload_text_file(filename: str, content: str, mimetype: str = "text/plain") -> str:
    """Uploads a text file into the configured shared folder, returns its file ID."""
    service = _get_service()
    file_metadata = {"name": filename, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode("utf-8")), mimetype=mimetype, resumable=False
    )
    try:
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        return file["id"]
    except HttpError as e:
        raise DriveError(f"Failed to upload '{filename}' to Drive: {e}") from e


def find_file_by_name(filename: str) -> Optional[str]:
    """Returns the file ID of a file with this exact name in the configured
    folder, or None if it doesn't exist yet."""
    service = _get_service()
    safe_name = filename.replace("'", "\\'")
    query = (
        f"'{settings.GOOGLE_DRIVE_FOLDER_ID}' in parents "
        f"and name = '{safe_name}' and trashed = false"
    )
    try:
        results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    except HttpError as e:
        raise DriveError(f"Failed to search Drive for '{filename}': {e}") from e

    files = results.get("files", [])
    return files[0]["id"] if files else None


def download_file_text(file_id: str) -> str:
    service = _get_service()
    try:
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue().decode("utf-8", errors="replace")
    except HttpError as e:
        raise DriveError(f"Failed to download file {file_id} from Drive: {e}") from e
