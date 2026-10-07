"""Regenerate the checked-in Mental Omega AP item/location snapshot."""

from pathlib import Path
import json

from Archipelago.catalogue_contract import build_snapshot
from Archipelago.mission_catalogue import generation_missions


OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "APWorld"
    / "mental_omega"
    / "catalogue.json"
)


def main():
    from randomizer.core.paths import GAME_ROOT
    if (GAME_ROOT / 'MapsMO' / 'Cooperative').is_dir():
        from randomizer.coop.catalogue import discover_coop_missions
        (Path(__file__).resolve().parent / 'generation_coop_missions.json').write_text(
            json.dumps(discover_coop_missions(GAME_ROOT), ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8', newline='\n',
        )
    existing = None
    if OUTPUT_PATH.is_file():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    snapshot = build_snapshot(existing)
    if not snapshot['missions']:
        raise ValueError('Refusing to write an APWorld catalogue without missions.')
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # Release CI has no copyrighted game installation. Retain the full
    # generation input alongside the item/location projection for that build.
    (Path(__file__).resolve().parent / 'generation_missions.json').write_text(
        json.dumps(generation_missions(), ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
        newline='\n',
    )
    print(
        f"{OUTPUT_PATH}: {len(snapshot['items'])} items, "
        f"{len(snapshot['locations'])} locations, "
        f"{snapshot['catalogue_checksum']}"
    )


if __name__ == "__main__":
    main()
