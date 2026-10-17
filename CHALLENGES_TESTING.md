# Challenge build 1.44.3

## Agent handoff

Custom source: https://github.com/ckbk456/Mental-Omega-Randomizer (main).
Upstream: https://github.com/Heinki/Mental-Omega-Randomizer.
Use this custom fork; the upstream release alone does not contain these changes.

Set up the brother's Windows PC as the guest. Khang is the host. Use a dedicated
Mental Omega 3.3.6 game folder with matching native files on both PCs. This repo
contains launcher source, not the game data. The currently verified gamemd.exe
SHA-256 is `7F798F3336AB370325AF29BDDDE90791CC9E097EF1928CF25B13DA7EC227F486`.
Do not substitute another engine silently; the runtime handshake compares it.

1. Clone the custom fork. Read `AGENTS.md`, `DEVELOPER_GUIDE.md`, and
   `tools/CHALLENGES-START-HERE.txt`. Keep the user's other coding projects out
   of this game setup. Do not add or run unit tests; use the existing operational
   checks and real map/log audits.
2. Build with Python 3.14.6 and `requirements-build.txt`, then run
   `build_exe.ps1 -Output '<GAME_FOLDER>\MentalOmegaRandomizer.exe'`. An existing
   Python 3.13+ runtime can use the explicit `-LocalTestBuild` switch. This path
   was validated with Python 3.13.2, PyInstaller 6.19.0 and websockets 17.0.
3. Run the new EXE with `--self-check` from the game folder; inspect
   `RandomizerLauncherData/self_check.json`. Do not start a game automatically.
4. Configure the guest's player YAML under
   `RandomizerLauncherData/configs/player/mental_omega_randomizer.yaml` with
   `player_name: Brother`, `coop_role: Join`, `mission_category: challenge`,
   `coop_mode: true`, `challenge_player_count: 2`,
   `coop_challenge_country: UnitedStates`, and `coop_challenge_color: Red`.
   These are defaults; the brother chooses his actual house/color in the lobby.
   Do not copy Khang's private saves, IP history, passwords or pairing codes.
5. Preserve an existing working private-network route. ZeroTier itself is an
   external dependency: if using it, install the official signed client, join
   the same network on both PCs, and authorize both members. The launcher does
   not create/join a ZeroTier network. Khang's PC currently has a Tailscale route;
   verify the actual private IPv4 rather than assuming a network ID or address.
6. Copy `tools/Setup-Private-Network.ps1` beside the built EXE. Run `-WhatIf`
   to inspect its rules and `-Elevate` to apply them with Windows administrator
   approval. It allows this folder's launcher TCP 19420/19421 and gamemd UDP 1234
   only on detected ZeroTier/Tailscale adapters. No router forwarding is needed.
7. Khang opens Host in Co-op Connection and privately supplies his VPN IPv4 and
   pairing code. Brother opens Join and enters them. Each chooses an allowed
   house and a different color. Host owns the run, difficulty and fixed speed;
   guest receives the same rewards and progress. Keep both launchers connected.

Khang's local host copy is already prepared for two-player challenges with
Chaos rewards, the existing starting unlock settings and speed **5 - Faster**.
His solo save is preserved separately. No ZIP or game-data transfer was created.
No Computer Use/gameplay automation is required for setup. Final live gameplay
validation still needs both people: connect, win a challenge, verify rewards on
both PCs, and quit. Real socket pairing, map generation/replay, native log
audits and packaged self-checks have been exercised locally.

This local build adds stock Mental Omega challenges to Classic, Mission List,
and Grid Mode, with earned randomized rewards, one local human with an optional
AI teammate, or two humans over the existing private-network connection.
Shop Mode and Archipelago challenge seeds are not included in this build.

Version 1.44.0 finishes the paired challenge setup. Each player selects their
own house/country and color in **Co-op Connection**. Different factions receive
their own production roster while sharing the host's run, unlocks and rewards.
The host sets game speed and difficulty; the paired game speed control is locked.
Map-specific enemy houses and colors stay reserved. Both players must use the
same build; the current build is 1.44.3.

Version 1.44.3 adds **Play with an AI teammate** for challenges with **Human
players: 1**. Select an open challenge, then choose your color and the AI's
allowed house, color and Easy/Normal/Hard difficulty under Local challenge
players. Launch Selected Mission starts locally without connecting to co-op or
Archipelago. The AI occupies the second allied start, uses its native army,
and has its own difficulty; the human keeps the run's earned rewards. Enemy
challenge difficulty remains the existing Casual/Normal/Mental setting.
These launch choices do not require a new seed. Two-human games keep their
existing connection flow and host-controlled speed.

Launch preparation now indexes native rules and INI section bounds instead of
repeatedly scanning them. Host and guest also reuse their locally validated map
when writing the game files. Both PCs still independently rebuild and verify
the selected map, native files and rewards before the game starts.

Measured build plus verified replay time on real saved runs fell from 8.37 to
1.64 seconds for the current paired run, 3.86 to 0.85 seconds for the solo run,
and 15.87 to 3.33 seconds for an archived run with 439 earned rewards. All nine
manifest/map outputs remained byte-identical. These measure launcher map
preparation, not native game loading or frozen executable startup. Actual AI
teammate gameplay still requires a live win/loss check; preparation audits
covered all 22 installed maps and existing native result logs.

Version 1.44.2 adds **Unlimited build-limited buildings** in Settings > Reward
Pool, independently of Unlimited unique / hero units. Enable it before
generating a standalone challenge, co-op, or campaign run. It removes nonzero
build caps from earned player defenses and special buildings, including their
private deploy/undeploy forms. It does not grant unearned building access,
remove prerequisites or electricity requirements, or alter native enemy caps.
Structure +1 rewards are omitted while this option is enabled. Shop Mode keeps
its existing capacity economy. The option defaults off for existing configs
and saves; an existing seed retains its saved choice.

Challenge colors now follow the authored enemy factions instead of the human
house fallback: Soviets red, Allies blue, Yuri/Epsilon purple, Foehn teal.
Endurance is Foehn/teal. Challenges XVII-XXII face mixed armies and use a moving
rainbow gradient drawn natively on Tk Canvas, with readable text and the normal
status badges. Animation pauses when hidden or minimized. These display fixes
apply to existing runs after reopening the updated launcher; they do not change
house eligibility, game rules, rewards or mission order.

Version 1.44.1 repairs native behavior of unlocked objects. Grumble and other
mode-switching units now bring their private deployed/converted definitions
and return links. Earned Reprocessors participate in the bounty enabler list;
Iron Guards and other building powers target their actual player clones.
Iron Guard still needs enough electricity, but does not need a second Iron
Curtain building to operate. Invisible implementation providers use the native
GALITE art's zero-cell foundation, so they no longer occupy build placement
cells. Their power ownership and trigger assignments remain intact.

The audit also repairs Prism Tower forwarding, refinery/miner docking, aircraft
pad capacity, deployed Boid powers, Signal Inhibitor references, Elite Reserves
Academy targets, and summoned/delivered helper ownership. Power payloads stay
private and unbuildable; their powers do not unlock independent production.
Earned building buffs now travel through both players' manifests and apply to
their actual buildings and weapons. Mastermind capacity and Opus passenger
upgrades are supported, and Stardust/Rejuvenator production gates are repaired.
Nanofiber evolution retains each player's private infantry and earned buffs;
the required art and early animation registrations are prepared before launch.
Large veteran rosters use compact IDs to stay within the native country limit.

Reopen the desktop shortcut after closing the old launcher. These changes apply
when preparing the next match; an already running game keeps its old map rules.
Existing earned rewards and save progress do not require a new seed for these
1.44.1 fixes. Both PCs should use the same current version before connecting.

Heavyobject is a valid, intact stock map. Its enemy houses include Last Bastion,
Euro Alliance and Epsilon HQ, so those player houses cannot use it. Two-player
catalogues now expose all 22 maps, with actual allowed houses selected per map
in the lobby. For a new run containing every challenge, use All Campaigns and
set Mission goal to 22. Existing 19-map saves retain their layout and progress;
they are not silently expanded. Solo house filtering remains and explains this
restriction in Settings. Haihead or Coronia can play Heavyobject.

Both launchers verify native team results. If the host is eliminated first,
the surviving guest can report a verified team victory for that exact game;
the host still owns progression and reward synchronization. Keep the host
launcher connected while the other player finishes.

Version 1.43.3 fixes **Unlimited unique / hero units** in challenges and ordinary
co-op. The saved run setting now reaches the generated player unit rules and
participates in both players' map verification. It removes simultaneous-unit
caps for the reviewed trainable hero/unique roster; special-building caps and
enemy unit caps retain their normal behavior. Close the game and launcher, then
reopen the desktop shortcut and relaunch the challenge. An existing run with
this option enabled needs no new seed.

Version 1.43.2 adds recovery for the observed black screen when quitting. After
the current session logs a processed Quit/EXIT and finishes its game loop, the
launcher allows normal cleanup, then closes that game's captured process tree
if cleanup remains stuck. Natural victory/defeat score screens alone do not
trigger this recovery, and shutdown records never grant victory rewards.

Game speed is now available beside **Launch Selected Mission**, including when
Details is hidden. Choose **4 - Fast**, **5 - Faster**, or **6 - Fastest** before
launching for faster play; the choice is saved and needs no new seed. The labels
now match Mental Omega's native speed direction. Two-player challenges use the
host's choice on both machines. Ordinary cooperative campaign speed is unchanged.

## Start a solo run

1. Open **Mental Omega Challenges Test** from the Windows desktop.
2. In Settings, select mission category **challenge**, **Human players: 1**, and a
   country. Country choices filter maps that prohibit that country or use it
   for an enemy. The 22 stock challenges are available across country choices;
   one country normally has 18 or 19 compatible maps.
3. Choose Classic, Mission List, or Grid Mode; choose Standard, Chaos, or
   Randomizer Arsenal rewards and the desired difficulty.
4. Click **Generate New Seed**, select an open challenge and choose **Game speed**.
   Under **Local challenge players**, choose your color. Optionally enable
   **Play with an AI teammate** and choose its house, different color and
   difficulty. Click **Launch Selected Mission** directly.

Basic unit and defense access is enabled when Challenges is first selected,
so the initial base-building challenge has a usable roster. Further unlocks
and buffs come from completed challenges. Changing country or player count
requires a matching new seed; existing saved runs are preserved separately.

## Check native behavior and results

- Native challenge difficulty, enemy countries, alliances, starting positions,
  scripted units and map-specific restrictions should match Mental Omega.
- The selected country must have its initial construction/production and
  basic combat access. Enemy challenge abilities must still work.
- Win by defeating every enemy. After the native game writes its final result
  statistics, the launcher should complete the challenge once and unlock its
  saved rewards. Depending on when the engine flushes statistics, return from
  the results screen before checking launcher progress.
- Losing, quitting an unfinished challenge, or crashing must not award a
  victory. A missing or ambiguous result remains uncompleted.
- Replaying an already completed challenge must not grant the same reward
  twice. Restarting the launcher should preserve challenge progress.

The result reader starts before each game and reads only fresh native log
data. A Winner row by itself is insufficient: installed unfinished games also
produce such rows. Paired and AI games require native completion, complete
statistics for the whole expected roster, at least one allied Winner and every
registered enemy marked Loser. An eliminated human can therefore receive team
credit if the remaining ally wins. AI rows follow native house order, with the
allied AI directly after the local human; ambiguous or incomplete rows award
nothing. Solo games retain their existing complete enemy-loss verification.

## Play with two people

Both players need this same custom executable and matching Mental Omega game
files, including `gamemd.exe`. Each launcher must have its own game folder.

1. Host: select **challenge**, **2** players, a mission-pool country and a
   progression mode; generate a seed. The pool country filters the available
   maps. Actual player houses are selected separately in the connection dialog.
2. Open **Co-op Connection**. Choose Host and a unique player name, connect,
   choose your own house and color, and provide the displayed pairing code to
   the other player together with your private-network IPv4.
3. Guest: open the same build, select a two-player mode, open the connection
   dialog, choose Join and a different player name, and enter the host's
   private IPv4 and pairing code. Select your own house and a different color.
   An existing authorized Tailscale or ZeroTier
   network can carry the connection. Do not configure router port forwarding.
4. The guest receives the host's challenge list, seed, progression and rewards.
   Both players' actual house/color choices appear in the dialog. The host
   selects a compatible challenge and game speed, then launches it. Incompatible
   houses or duplicate/reserved colors produce an explanation before launch.
   Both games use the host's speed and difficulty.
5. Both peers independently rebuild and hash the prepared map before starting.
   A verified host victory publishes progression and rewards to the guest.

For a same-PC paired trial, a second copy and desktop shortcut named
**Mental Omega Challenges Guest Test** have also been prepared. Join
`127.0.0.1`. The existing transport automatically separates game ports.
The two copies must not share `spawn.ini`, `spawnmap.ini`, or runtime data.

## Diagnostics and build

The test installation uses its own `RandomizerLauncherData`, with
`challenge_solo_state.json` and `challenge_coop_state.json` as separate saves.
Useful reports are `RandomizerLauncherData/logs/launcher.log` and the native
`debug/debug.log`. Retain both when reporting a challenge failure.

The source is based on upstream commit
`7078843a0ffee3f17a8b7c98b438a25c1cd4fe41`. Official packaging still requires
the repository's pinned Python 3.14.6 runtime. The explicit `-LocalTestBuild`
switch also accepts an existing Python 3.13+ runtime for local validation;
it retains static-config, compilation and Tcl/Tk archive checks.

Follow `AGENTS.md`: use compilation, existing installation/domain self-checks,
installed-map audits and gameplay checks. Do not add or run unit-test suites.

## Checks completed for the challenge feature

- Packaged installation/domain self-check: passed, exit code 0.
- Native option patches: all 22 maps at all three difficulty levels.
- Map manifests and deterministic replay: all 22 maps with one and two humans;
  all twelve player countries and all three difficulties represented.
- Native Foehn Standard starters: all three countries, solo and paired.
- Existing cooperative campaign parity audit: passed.
- Actual launcher startup: 19 compatible Euro Alliance challenges, correct
  starter preset, supported mode controls, no callback errors.
- Actual native log results: one completed paired match emitted victory once;
  twenty archived unfinished matches produced no verified victory.
- Existing direct connection tool: real loopback host/guest dry run passed;
  both installations prepared byte-identical maps and the same game ID.

These checks do not replace live gameplay of the new challenge mode. Test a
solo win, an unfinished quit, and a paired win before relying on a long run.

The 1.43.2 quit recovery is based on the observed native quit log. Live validation
of the new recovery is pending; this update does not automate game interaction.

Additional 1.43.2 validation: all seven speed labels match the installed native
client; 88 installed challenge preparations (22 maps, one/two humans, both speed
extremes) passed with real saved rewards and deterministic replay. Actual solo
runtime preparation and TCP host/guest pairing verified matching selected
speeds, with the original runtime files restored afterward. Existing schema 6
manifests remain compatible.

Additional 1.43.3 validation: the real saved run was prepared with the option
off/on for Regenbogen solo, Regenbogen paired, Allied Balance, and Ablution.
All 16 map generations, including peer rebuilds, matched. Exactly 23 earned
hero/unique player sections lost their BuildLimit; native originals, enemies,
buildings, providers, and other sections were identical between settings.
The existing roster validator passed all 34 reviewed hero/unique unit types.
Packaged installation/domain checks passed in both test installations.

Version 1.44.0 validation includes 66 paired installed-map preparations across
all 22 maps and all three reward modes, with same/cross-faction countries,
Foehn starters, every difficulty and host-speed extremes. Deterministic peer
rebuilds passed. Real TCP preparation and authenticated lobby message exchange
passed between separate game folders, including reversed human color order.
These checks prepare runtime files without launching or automating a game.

Version 1.44.1 validation includes the complete earned mobile/building catalogue,
private deploy/conversion dependencies, all 93 reward powers across all 22 stock
challenge maps, deterministic host/guest rebuilds, and staged mutation artwork.
The existing saved 19-map run regenerates without modifying its progress;
Reprocessor enablers contain both human clones and hidden providers have zero
build-placement footprint. Large catalogue veteran lists fit the configured
native limit after aliasing. Compilation and packaged checks supplement these
map audits. Live ability behavior still needs player verification in the game.
