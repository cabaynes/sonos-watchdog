"""Optional friendly names for speaker radio MACs, from a git-ignored local file.

tools/labels.local.json: {"AA:BB:CC:DD:EE:FF": "Kitchen", ...}
"""
import json
import sys
from pathlib import Path

DEFAULT = Path(__file__).with_name("labels.local.json")


def load(path=DEFAULT) -> dict:
    try:
        return {k.upper(): v for k, v in json.loads(Path(path).read_text()).items()}
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, AttributeError) as e:
        print(f"warning: ignoring {Path(path).name} ({e}); showing MACs instead of names", file=sys.stderr)
        return {}
