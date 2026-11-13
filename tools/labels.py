"""Optional friendly names for speaker radio MACs, from a git-ignored local file.

tools/labels.local.json: {"AA:BB:CC:DD:EE:FF": "Kitchen", ...}
"""
import json
from pathlib import Path

DEFAULT = Path(__file__).with_name("labels.local.json")


def load(path=DEFAULT) -> dict:
    try:
        return {k.upper(): v for k, v in json.loads(Path(path).read_text()).items()}
    except FileNotFoundError:
        return {}
