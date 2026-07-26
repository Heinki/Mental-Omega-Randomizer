# Player Configuration

The launcher writes `mental_omega_randomizer.yaml` here during source runs.
Packaged builds use
`RandomizerLauncherData/configs/player/mental_omega_randomizer.yaml`.

This YAML contains local next-seed, UI, launch, and reserved Archipelago
settings. It is ignored by Git and excluded from packaged build inputs. Static
gameplay policy belongs in the parent `configs/` directory or
`configs/rewards/`.

Older `config/mental_omega_randomizer.yaml` files move here automatically on
first load when this directory has no active YAML.
