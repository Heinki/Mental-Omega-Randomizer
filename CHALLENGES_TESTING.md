# Native challenges — 1.44.5

The launcher supports all 22 stock Mental Omega challenges with earned
randomized rewards in **Classic**, **Mission List**, and **Grid Mode**.
Choose one local human, one human with an optional AI teammate, or two humans
connected over a private network. **Shop Mode and Archipelago challenge seeds
are not supported.** Ordinary cooperative campaign missions require two humans.

## Installation and updates

Use a complete, writable, clean Mental Omega 3.3.6 installation. Verify that a
stock mission runs normally, then put `MentalOmegaRandomizer.exe` beside
`MentalOmegaClient.exe`, `gamemd.exe`, and `Syringe.exe`. This repository contains
launcher source; it does not supply the game. A packaged launcher needs no
separate Python installation. Custom maps, map packs, rules edits, and mixed
mod installations are outside the audited baseline.

Close the previous launcher before updating its EXE or shortcut. Preserve
`RandomizerLauncherData`: it contains the player's settings, saves, and caches.
Existing earned rewards and progress carry forward. Both multiplayer peers
must use the same launcher version and matching native game files; the launch
handshake checks the engine, relevant rules, metadata, and prepared map.
Do not distribute another player's profile or private connection information.

## Start a local challenge

1. In **Settings**, choose mission category **challenge** and **Human players: 1**.
2. Choose Classic, Mission List, or Grid Mode; Standard, Chaos, or Randomizer
   Arsenal rewards; and the desired challenge difficulty.
3. Generate a seed or continue a saved solo run. To include every challenge in
   a new run, use **All Campaigns**, a **Mission goal of 22**, and no map exclusions.
4. Select an open challenge. Under **Local challenge players**, choose
   **Your house** and **Your color**.
5. Optionally enable **Play with an AI teammate** and choose its house, a
   different color, and **Easy / Normal / Hard** difficulty.
6. Choose **Game speed** beside the launch button, then click
   **Launch Selected Mission**. A local game needs no co-op or Archipelago connection.

The AI takes the second allied starting position and uses its native army;
only the human receives the run's earned technology and buffs. AI difficulty
is independent of the challenge enemies' **Casual / Normal / Mental** difficulty.
Basic unit and defense starters are enabled when challenges are first selected.

Human and AI houses, colors, AI difficulty, and game speed are launch preferences:
changing them does not regenerate the seed, reroll rewards, or clear progress.
All 22 maps remain in the catalogue regardless of the selected house. Selections
stay unchanged when switching maps. Before preparing a game, the launcher checks
both houses and colors against the selected map and explains conflicts with
allowed alternatives. Allies may use the same house but need distinct permitted
colors. For example, Heavyobject reserves Last Bastion, Euro Alliance, and
Epsilon HQ for enemies; those players must choose another house for that match.

Speed labels follow the native client: **4 - Fast**, **5 - Faster**, and
**6 - Fastest** accelerate play. Ordinary cooperative campaign speed is unchanged.

## Play with two humans

Each player needs a separate matching game installation and the same launcher.
Use an existing authorized ZeroTier or Tailscale network; network installation,
member authorization, and optional firewall setup are described in
[Co-op Connection Guide](COOP_CONNECTION_GUIDE.md).

1. Host: select **challenge**, **Human players: 2**, a progression mode, and
   reward settings, then generate or continue a two-player seed.
2. Open **Co-op Connection**, choose **Host**, enter a player name, and connect.
   Share the displayed pairing code and the host's private-network IPv4 privately.
3. Guest: select challenge with two humans, open the same dialog, choose **Join**,
   enter a different player name, and connect using the host's IPv4 and pairing code.
   Human names must not be `Computer`, which is the native AI result name.
4. Each player chooses a house and color in the dialog. Either can change houses
   between matches without resetting the shared run. Launch preflight checks
   both selections against the map, including enemy house and color reservations.
5. The host selects and launches an open challenge. The guest can suggest maps.
   Both games use the host's difficulty and pinned game speed. Keep both
   launchers connected while playing and while results synchronize.

The host owns the seed, progression, and shared reward inventory. Each human
receives the appropriate production roster for their selected country. Both
peers independently rebuild and verify the map before starting. If the host is
eliminated first, a verified surviving guest victory can still advance that
exact shared game; the host launcher must remain connected.

## Rewards and saved runs

**Unlimited unique / hero units** removes simultaneous-unit caps from the
reviewed earned mobile roster. **Unlimited build-limited buildings**, under
**Settings > Reward Pool**, independently removes nonzero caps from earned
player defenses and special buildings, including their private deploy forms.
Enable these generation options before creating a run; an existing seed keeps
its saved choices. Unlimited buildings omits Structure +1 rewards. Neither
option grants unearned technology, removes normal prerequisites or electricity
requirements, or changes enemy caps. Shop retains its capacity economy.

Earned objects retain their native mechanics through private player definitions:

- Grumble and other deploying or converting units keep their alternate forms
  and return links. Nanofiber evolution keeps private infantry and earned buffs,
  with the required animation art staged before launch.
- Reprocessor bounty enablers and Iron Guard, Boid, and other building powers
  refer to the actual player buildings. Iron Guard needs electricity, but no
  separate Iron Curtain building.
- Prism forwarding, refinery/miner docking, aircraft pads, Signal Inhibitors,
  Academy targets, summoned helpers, and delivered units retain their native
  relationships. Helper payloads remain unbuildable.
- Building and weapon buffs follow each human's roster. Mastermind capacity,
  Opus passengers, Stardust/Rejuvenator production access, and compact veteran
  aliases are included in the native compatibility handling.
- Invisible implementation providers use zero-cell art foundations, preserving
  their ownership and effects without occupying building placement cells.

Challenge tile colors identify the authored enemy factions: Soviet red, Allied
blue, Epsilon purple, and Foehn teal. Endurance is Foehn. Mixed challenges
XVII–XXII use an animated Tk Canvas rainbow; animation pauses while hidden or
minimized. Display colors do not change gameplay restrictions.

One-human and two-human challenge runs have separate saves. Whole former
18/19-map house-filtered solo runs can gain their omitted maps through a backed-up
migration. Existing order, completed checks, reward assignments, grid positions,
and original goal remain intact; only added maps receive new checks. Deliberately
shorter runs and explicit map exclusions retain their plans. Normal progression
locks still apply, and replaying a completed challenge grants no duplicate reward.

## Completion, quitting, and diagnostics

Challenge results come from fresh native `debug/debug.log` records. A Winner row
alone is insufficient: unfinished native games can print that row. Paired and
AI games require native completion, complete expected statistics, every enemy
marked Loser, and at least one allied Winner. An eliminated human can receive
team credit if the remaining ally wins. AI score rows follow native house order,
with the allied AI directly after the local human. Solo games retain complete
enemy-loss verification. Missing, ambiguous, crashed, or unfinished results grant
no victory; returning from the score screen may be needed before statistics flush.

Quit recovery waits for a processed Quit/EXIT record and the game loop to finish.
If that launched game's captured process tree still fails to clean up, the
launcher closes that tree after a grace period. A normal victory/defeat screen
does not trigger recovery, and shutdown records do not grant rewards.

Run `MentalOmegaRandomizer.exe --self-check` from the game directory. Inspect
`RandomizerLauncherData/self_check.json` for the expected `app_version` and
`passed: true`. Keep these diagnostics when reporting a problem:

- `RandomizerLauncherData/logs/launcher.log` and `self_check.json`;
- native `debug/debug.log`;
- mission code, seed, reward mode, player houses, and whether AI or a peer was used.

Packaged saves are `RandomizerLauncherData/challenge_solo_state.json` and
`challenge_coop_state.json`. Review saves and native logs before sharing; they
can contain progress or private network details.

## Maintainer build and validation

Read `AGENTS.md` and [Developer Guide](DEVELOPER_GUIDE.md). Official Windows
packaging requires **Python 3.14.6** and the pinned `requirements-build.txt`.
From the source checkout:

```powershell
python -m pip install -r requirements-build.txt
.\build_exe.ps1 -Output '<GAME_FOLDER>\MentalOmegaRandomizer.exe'
```

For local validation with an existing **Python 3.13+** installation, the explicit
`-LocalTestBuild` switch permits that runtime. It still checks static configs,
compiles source, and verifies the bundled Tcl/Tk archive. This exception does
not change the official release runtime or dependency pins.

Use compilation, the existing packaged installation/domain self-check, the
existing `tools/check_coop_parity.py` audit, installed-map audits, and manual
play as appropriate. Do not add or run unit-test suites under the current
repository policy. A self-check prepares no gameplay session.

Recorded development coverage includes all 22 native maps and three challenge
difficulties; one-human, local-AI, and two-human preparation; all twelve player
countries; three reward modes; speed extremes; Foehn starters; deterministic
manifest replay; the earned unit/building catalogue and 93 reward powers;
private deployment and mutation art; and native reward isolation. Real loopback
lobby/preparation checks used separate game directories, matching game IDs and
byte-identical maps, including reversed human color order. Archived native logs
were audited for verified results and unfinished games without awarding false wins.

Native-rule/INI indexing and reuse of each peer's validated map reduce repeated
preparation work. Sample build-plus-replay measurements fell from 8.37 to 1.64,
3.86 to 0.85, and 15.87 to 3.33 seconds across three saved rosters; all nine
manifest/map outputs remained byte-identical. These measure map preparation,
not frozen launcher startup or native game loading.

These checks do not establish complete live gameplay coverage. A local AI win
and loss, a sustained two-PC session with synchronized rewards, restored native
ability behavior, and quit recovery still need player verification on the target
installations. Loopback preparation does not establish Windows/Linux gameplay
compatibility over a private network.
