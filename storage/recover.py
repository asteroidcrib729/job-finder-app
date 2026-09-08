"""Export a validated recovery candidate without replacing live history."""
import argparse
import json
from pathlib import Path
from storage.reconcile import validate_discovery_state
from storage.tracker import StateError, read_json, validate_delivery_state


def export_recovery(backup, output, kind="delivery"):
    backup, output = Path(backup), Path(output)
    if not backup.is_file():
        raise StateError("Backup file does not exist")
    state = read_json(backup, {})
    validator = validate_delivery_state if kind == "delivery" else validate_discovery_state
    state = validator(state)
    if output.exists() or backup.resolve() == output.resolve():
        raise StateError("Recovery output must be a new file; original history is retained")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects an existing candidate from accidental replacement.
    with output.open("x", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kind", choices=("delivery", "discovery"), default="delivery")
    args = parser.parse_args()
    try:
        state = export_recovery(args.backup, args.output, args.kind)
    except (StateError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    if args.kind == "delivery":
        print(f"Recovery candidate: {len(state['seen'])} seen IDs, {len(state['pending'])} pending jobs.")
        print("Reconcile receipts after the backup with Discord and Git history before replacing live state; missing acknowledgements can resend alerts.")
    else:
        print("Validated discovery recovery candidate exported.")


if __name__ == "__main__":
    main()
