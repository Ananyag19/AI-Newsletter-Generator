"""
Run this ONCE to authorize the backend to read/write Google Drive as YOUR
OWN Google account — the same one you connected to Grok's Drive connector
at grok.com/tasks. This is what the grok_drive AI provider relies on.

Why not a service account: Google gives service accounts zero Drive storage
quota, so they fail with a 403 "Service Accounts do not have storage quota"
error the moment they try to create a file — even in a folder explicitly
shared with them as Editor. Authenticating as a real user sidesteps this
entirely, and you still only do this consent step once: the resulting
token file is refreshed silently by google_drive.py on every later run.

Setup before running this:
  1. In Google Cloud Console, open your project (or create one) and enable
     the Google Drive API (APIs & Services > Library > "Google Drive API").
  2. Go to APIs & Services > Credentials > Create Credentials > OAuth
     client ID. Application type: "Desktop app". Download the resulting
     JSON file.
  3. Save that file somewhere (e.g. backend/credentials/oauth_client.json)
     and set GOOGLE_OAUTH_CLIENT_SECRETS_FILE in .env to its path.
  4. Make sure GOOGLE_OAUTH_TOKEN_FILE in .env points at where you want the
     resulting token saved (default: ./credentials/drive_token.json).

Usage (from the backend/ directory):
  python scripts/get_drive_token.py

This opens your default browser for a one-time Google sign-in + consent
screen. Sign in with the SAME Google account connected to Grok. After you
approve, the script saves a token file and you're done — you won't need to
run this again unless you revoke access or delete the token file.
"""
import sys
from pathlib import Path

# Allow running this script directly (adds backend/ to the import path so
# `from config import settings` resolves regardless of cwd).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from config import settings  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> None:
    if not settings.GOOGLE_OAUTH_CLIENT_SECRETS_FILE:
        print(
            "GOOGLE_OAUTH_CLIENT_SECRETS_FILE is not set in .env.\n"
            "Point it at the OAuth client JSON you downloaded from Google Cloud Console "
            "(Credentials > OAuth client ID > Desktop app)."
        )
        sys.exit(1)

    client_secrets_path = Path(settings.GOOGLE_OAUTH_CLIENT_SECRETS_FILE)
    if not client_secrets_path.exists():
        print(f"Could not find {client_secrets_path}. Check the path in .env.")
        sys.exit(1)

    print("Opening your browser for Google sign-in... ")
    print("Sign in with the SAME Google account you connected to Grok's Drive connector.")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = Path(settings.GOOGLE_OAUTH_TOKEN_FILE or "./credentials/drive_token.json")
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

    print(f"\nDone. Token saved to {token_path}.")
    print("You won't need to run this script again unless you revoke access or delete that file.")


if __name__ == "__main__":
    main()
