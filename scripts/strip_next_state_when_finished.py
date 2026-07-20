"""One-off cleanup: remove the dead physics.next_state_when_finished
field from sprite config.json files under assets/pieces/. The engine
already owns state transitions exclusively (see UI_PLAN.md Sec 5) so
this field is a false second source of truth. Safe to re-run.

Usage:
    python scripts/strip_next_state_when_finished.py [--dry-run]
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_GLOB = "assets/pieces/*/states/*/config.json"


def main():
    dry_run = "--dry-run" in sys.argv
    paths = sorted(REPO_ROOT.glob(CONFIG_GLOB))
    changed_count = 0

    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if "next_state_when_finished" not in data.get("physics", {}):
            continue
        changed_count += 1
        if dry_run:
            print(f"would strip: {path.relative_to(REPO_ROOT)}")
            continue
        data["physics"].pop("next_state_when_finished")
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    verb = "would strip" if dry_run else "stripped"
    print(f"{verb} next_state_when_finished from {changed_count}/{len(paths)} file(s)")


if __name__ == "__main__":
    main()
