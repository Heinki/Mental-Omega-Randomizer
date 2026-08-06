"""Regenerate the checked-in Mental Omega AP item/location snapshot."""

from pathlib import Path
import json

from Archipelago.catalogue_contract import build_snapshot


OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "APWorld"
    / "mental_omega"
    / "catalogue.json"
)


def main():
    existing = None
    if OUTPUT_PATH.is_file():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    snapshot = build_snapshot(existing)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"{OUTPUT_PATH}: {len(snapshot['items'])} items, "
        f"{len(snapshot['locations'])} locations, "
        f"{snapshot['catalogue_checksum']}"
    )


if __name__ == "__main__":
    main()
