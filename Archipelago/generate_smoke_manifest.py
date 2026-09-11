"""Export reusable settings from a generated run as an AP smoke YAML."""

from pathlib import Path
import argparse

from Archipelago.run_manifest import build_run_manifest
from Archipelago.yaml_config import serialize_player_yaml
from randomizer.config.player import load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("state", nargs="?", default="randomizer_state.json")
    parser.add_argument(
        "--yaml",
        default="Archipelago/smoke/mental_omega.yaml",
    )
    args = parser.parse_args()
    import json
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    manifest = build_run_manifest(state, load_config())
    output = Path(args.yaml)
    output.write_text(
        serialize_player_yaml(manifest, "MOFullSmoke"),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"{output}: settings only; Archipelago will generate the run "
        f"({sum(manifest['item_pool'].values())} source locations validated)"
    )


if __name__ == "__main__":
    main()
