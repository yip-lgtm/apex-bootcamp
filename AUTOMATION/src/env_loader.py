"""env_loader: dotenv + ${VAR} expansion.

python-dotenv does NOT expand ${VAR} syntax — it just reads the literal value.
This module reads the .env file manually and expands ${VAR} from:
  1. parent process env (highest priority)
  2. values already loaded earlier in the .env file
  3. default empty string

Usage:
    from env_loader import load_env
    load_env()  # loads .env from AUTOMATION root
    API_KEY = os.environ.get("MINIMAX_API_KEY")
"""
from __future__ import annotations
import os
import re
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand(value: str, env: dict) -> str:
    """Expand ${VAR} tokens from the env dict."""
    def repl(m):
        k = m.group(1)
        return env.get(k, "")
    return _VAR_RE.sub(repl, value)


def load_env(path: Path | str | None = None) -> dict:
    """Load .env into os.environ, expanding ${VAR}.

    Returns the dict of values loaded.
    """
    p = Path(path) if path else _ENV_FILE
    if not p.exists():
        return {}
    loaded: dict[str, str] = {}
    with p.open() as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip()
            # Strip surrounding quotes if present
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            # First pass: expand from existing os.environ + already-loaded
            v = _expand(v, {**os.environ, **loaded})
            loaded[k] = v
            # Don't overwrite parent env unless explicit
            if k not in os.environ:
                os.environ[k] = v
    return loaded


if __name__ == "__main__":
    d = load_env()
    print(f"Loaded {len(d)} vars from {_ENV_FILE}")
    for k in ("MINIMAX_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GITHUB_PAT"):
        v = os.environ.get(k, "<missing>")
        masked = v[:6] + "..." + v[-4:] if len(v) > 12 else v
        print(f"  {k} = {masked}")
