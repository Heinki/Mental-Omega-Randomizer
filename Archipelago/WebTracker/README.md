# Mental Omega website tracker

This is a website-only integration for Archipelago's Python/Flask WebHost, targeting
the tracker API used by Archipelago 0.6.8. It shows faction/category cameo cards,
received and starting items, descriptions, base unit/weapon stats, capped reward
stacks, current and next-stack effects, combined health/armor durability, mission
checks and Shop checks. Search and a received-only filter work without reloading.
Cards use the same 60×48 artwork extraction and reward display calculations as
the launcher's Details/Unlocks view. Buff receipt does not grant unit access.

## Why the APWorld alone does not enable it

Archipelago's WebHost chooses a renderer from `_player_trackers` in
`WebHostLib/tracker.py`, falling back to `genericTracker.html` for unknown games.
SC2 has a renderer registered there, an HTML template, JavaScript and image URLs.
`WebWorld` settings and files inside an uploaded `.apworld` do not automatically
register a custom website renderer. See the upstream
[tracker implementation](https://github.com/ArchipelagoMW/Archipelago/blob/main/WebHostLib/tracker.py).

Mental Omega already exports the information this tracker needs: item IDs/names,
the signed run manifest, starting items/access, mission order, reward locations
and private victory-marker IDs. The WebHost supplies received inventory, starting
inventory, checked locations, aliases and goal status. No new slot-data version,
item IDs, gameplay rules or launcher UI changes are required.

Installing the APWorld on your generator or game server cannot change
**archipelago.gg**. That site's operators must accept and deploy a WebHost change
and its static assets. This bundle can be installed on a WebHost you control or
used as the implementation for an upstream contribution. It does not patch the
public website from a player's browser.

## Build

From `RandomizerLauncher`, using the matching launcher/APWorld source release:

```sh
python Archipelago/WebTracker/build.py
```

The default output is `build/mental-omega-webtracker`. The exporter reads the
existing AP catalogue for stable network IDs, uses the launcher's reward
definitions for presentation, and copies PNG cameos from the installed game's
archives/custom sidebar assets. It does not regenerate the AP catalogue or
rebuild the APWorld. No Flask dependency is needed to export.

To open an offline design preview with explicitly labeled sample inventory,
use Python with Jinja2 installed:

```sh
python build/mental-omega-webtracker/preview.py
```

Open `build/mental-omega-webtracker/preview.html` in a browser. It uses the real
exported images and presentation data; navigation and live room updates are
disabled in this preview.

`missing-cameos.json` lists entities for which no image could be extracted. Those
cards remain usable with labeled placeholders. To build on a machine without
Mental Omega installed:

```sh
python Archipelago/WebTracker/build.py --no-images --output build/webtracker-metadata
```

For a complete image bundle, build beside the game installation. Rebuild after
changing reward tuning or cameo sources. Keep the tracker bundle matched to the
launcher release: the tracker uses exported base values, not live game files on
the web server. Game artwork is extracted locally; confirm permission to
redistribute it before proposing those assets for public hosting.

## Install on your WebHost

Stop your WebHost, then run the generated bundle's installer:

```sh
python build/mental-omega-webtracker/install.py /path/to/Archipelago
```

It copies the renderer, generated presentation JSON, template, CSS, JavaScript
and PNGs into that checkout's `WebHostLib`, then adds one registration block at
the end of `tracker.py`. The first installation saves
`tracker.py.before-mental-omega`; reinstalling updates assets without duplicating
registration. Restart the WebHost and open the normal Mental Omega player
tracker URL: `/tracker/<tracker-id>/<team>/<player>`.

This is the Python website source checkout, not `custom_worlds` or the standalone
MultiServer installation. A self-hosted game server alone does not run a website
tracker. The WebHost must already have the room/seed and the matching Mental
Omega APWorld installed for its ordinary room hosting workflow.

To remove the integration, delete the marked registration block from
`WebHostLib/tracker.py` and restart. Restore the backup only if no unrelated
tracker changes have happened since installation. The copied assets can then be
removed. Upstream WebHost upgrades may replace `tracker.py`; rerun the installer
after checking compatibility.

## Behavior and limits

- AP's inventory method already includes precollected items; these are counted
  once, not added again from the manifest.
- Cards are selected from this seed's item pool and starters. Additional received
  items remain visible. Old/unrecognized rewards appear as plain received rows.
- Starting unit/defense IDs and always-available technologies show starting
  access. Other access comes only from access rewards. A buff can be received
  while its corresponding unit or power remains locked.
- Descriptions and per-reward values come from the launcher. Counts are capped
  at the launcher's stack limits for displayed effects; raw receipt counts stay
  visible. Health and armor additionally show their combined effective HP.
- Per-reward effects are not a full simulation of mission overrides, inherited
  payload buffs, shared role buffs or temporary Arsenal loadouts. The launcher
  remains authoritative for what a mission actually applies.
- Mission/Shop check totals exclude local victory logic markers, using the
  slot's explicit mappings. The generic tracker link retains access to hints,
  all received items and the original location table.
- Same-origin refresh follows the WebHost's saving second (normally once per
  minute), pauses while hidden and preserves open cards, search and scroll.
  A failed refresh keeps the last successful page and retries.
- No check/item placements or unrevealed reward sources are shown; the tracker
  reads public inventory and checked-location state only.

## Public-site contribution

Submit the renderer, template, style/script and generated presentation data to
the Archipelago maintainers. Replace the installer registration block with the
project's usual game-specific registration in `tracker.py`. Decide with the
maintainers whether to ship approved cameos as static files or host them at an
approved stable URL. Do not submit local caches, personal room data or the game
installation. Existing rooms already carry the data needed by this renderer;
deployment does not require regenerating their seeds.
