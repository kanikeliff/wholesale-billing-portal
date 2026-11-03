"""Load only Team A settings from the ignored repository-local .env file."""
import os
from pathlib import Path
import shlex


TEAM_A_VARIABLES = {
    "USE_MOCK_TEAM_A", "TEAM_A_BASE_URL", "TEAM_A_API_KEY", "TEAM_A_TIMEOUT",
}


def load_team_a_environment(path=None):
    path = Path(path) if path is not None else Path(__file__).resolve().parents[2] / ".env"
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        name, separator, value = line.strip().removeprefix("export ").partition("=")
        name = name.strip()
        if not separator or name not in TEAM_A_VARIABLES:
            continue
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            raise RuntimeError(f"Invalid local configuration for {name}.") from None
        if len(parts) > 1:
            raise RuntimeError(f"Quote the local configuration value for {name}.")
        os.environ.setdefault(name, parts[0] if parts else "")
