"""Run in your own terminal: the API key is read without echo or shell history."""
import getpass
import os
from pathlib import Path
import shlex
import sys
import tempfile


BASE_URL = "https://team-a-api-production.up.railway.app"


def save_configuration(path, api_key):
    path = Path(path)
    if not api_key or any(character.isspace() for character in api_key):
        raise ValueError("Enter a nonempty API key without whitespace.")
    values = {
        "USE_MOCK_TEAM_A": "false",
        "TEAM_A_BASE_URL": BASE_URL,
        "TEAM_A_API_KEY": api_key,
        "TEAM_A_TIMEOUT": "30",
    }
    existing = path.read_text().splitlines() if path.exists() else []
    retained = [line for line in existing
                if line.strip().removeprefix("export ").partition("=")[0].strip() not in values]
    content = "\n".join(retained + [f"{name}={shlex.quote(value)}" for name, value in values.items()]) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    if not sys.stdin.isatty():
        raise SystemExit("Run this helper in your own terminal for hidden key entry.")
    api_key = getpass.getpass("Team A API key (hidden): ")
    try:
        save_configuration(Path(__file__).resolve().parents[2] / ".env", api_key)
    except ValueError as error:
        raise SystemExit(str(error)) from None
    print("Saved Team A configuration to the ignored root .env with permissions 0600.")
    print("Restart Django to load it. Existing exported variables take precedence.")


if __name__ == "__main__":
    main()
