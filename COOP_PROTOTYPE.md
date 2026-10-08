# ZeroTier co-op prototype

Player co-op connections use a private ZeroTier network. The randomizer hosts
and joins over its managed IPv4 addresses. `MentalOmegaClient.exe` and the
CnCNet service are not used. The launcher shares run state over TCP, prepares
matching co-op maps on both computers, writes `spawn.ini` and `spawnmap.ini`,
then starts the game through `Syringe.exe`. The game uses UDP between players.
Co-op controls are hidden in release builds. For developer test builds, set
`COOP_FEATURE_ENABLED = True` in `randomizer/coop/feature.py` and rebuild the
launcher on both computers. Release builds cannot expose co-op through the UI
or saved settings. Keep the constant `False` for release builds.

## Start a co-op run

1. Install the same Mental Omega patch and randomizer executable on both
   computers. Each player must have a separate game folder. On one computer,
   use separate Wine prefixes too; opening two launchers from one game folder
   overwrites the same spawn files and cannot start two games.
2. On the host, check **Co-op mode (2 players)** in the normal Settings page.
   Select Classic, Mission List, or Grid Mode and any supported reward mode.
   Set campaign, difficulty, rewards, and mission goal as usual. Generate a
   seed. Co-op and campaign progress are saved separately.
3. In **Advanced → Missions**, search and include/exclude the installed co-op
   missions. The catalogue currently contains 36 registered two-player maps:
   12 Allied, 12 Soviet, and 12 Epsilon. The existing campaign filter also
   narrows this pool. Configure the pool before generating the seed.
4. Check **Co-op mode (2 players)** on the guest. Join and authorize both PCs
   on the same private ZeroTier network. Open **Co-op Connection…** on both
   launchers and use distinct names. Host selects **Host**, copies its visible
   pairing code and clicks **Connect**. Guest selects **Join**, pastes the
   host's **ZeroTier Managed IPv4** and pairing code, then clicks **Connect**.
   Guest inputs are masked by default and still accept paste. Ports are automatic.
   See [COOP_CONNECTION_GUIDE.md](COOP_CONNECTION_GUIDE.md) for setup and diagnostics.
5. Guest receives host's saved run and Grid. Both see the same map order,
   unlocks, rewards, and host-selected mission. A guest can click a map or use
   **Suggest Mission**; suggestion appears in host log and connection dialog.
   Host selects the playable map and clicks **Launch Selected Mission**. Both
   games start automatically after source-map and patch-version checks.

The lobby stays connected after the game closes. Co-op win actions now write
a unique marker to the host game debug log. When detected, the host records
victory and syncs the updated Grid and rewards to the guest. This is
experimental: an actual full-map victory has not yet been tested. Host can
still use **Record Co-op Victory** if the marker is missing. Only host can
generate a seed, launch a game, or record completion. Guest's own saved run
remains untouched and returns after disconnecting.

Two local games start, and a temporary startup trigger produced the marker in
the actual host game log. This confirms the marker logging path; a normal
co-op win and resulting Grid update still need a player playtest. The host
watcher handles debug-log truncation between games.

Each player receives the same earned infantry, vehicle, aircraft, naval, and
building access, earned powers, supported unit buffs, and shared
starting-credit bonuses. Enemy country buffs and AI powers are map-local;
enemy unit-tier buffs apply only to native types safe from player ownership.
Randomizer Arsenal uses the selected co-op mission's arsenal. If no access is
earned, a logged `FV` test grant lets the first map launch. The prototype does
not yet have a completed two-player playtest for these effects. Native co-op
map technology remains available. Shop Mode is described separately below.

## Co-op Shop Mode work

The installed 36 co-op maps form a deterministic Shop mission pool for
stages 1–10, including the opening stages and faction filters. They currently
use the Act 1 reward class because the co-op catalogue has no Shop difficulty
classification. This is a provisional economy choice, not a claim that every
map has Act 1 difficulty.

1. In **Shop Setup**, check **Co-op mode (2 players)** on both launchers before
   starting a Shop run. Use separate game folders. Type the same Shop seed on
   both computers, then start separate runs at the same stage. Each player
   keeps their own profile, Ore, starting units, purchases, and buffs.
2. Open **Co-op Connection…** in Shop Setup and connect as host and guest. The
   host's co-op mission offers, rerolls, selection, commitment, and difficulty
   assist sync to the guest. The guest can buy their own loadout but cannot
   change the mission. Different seeds, stages, or completed mission histories
   are rejected.
3. Host clicks a mission card to **Select**, clicks again to **Commit**, then
   waits for the guest acknowledgement and clicks **Launch Co-op Mission**.
   Both games start directly through the randomizer. The guest sends a
   validated private reward snapshot; the host builds one map with both
   loadouts.

The host's in-game victory marker records victory for both separate Shop runs.
Closing the host game without a victory marker records a failure in both
players' separate runs. If the host has Emergency Revival, both runs return to
the same stage and receive the host's new mission offers; each player's Ore,
purchases, and profile stay private. Closing the guest game first waits for the
host result. Failure messages are safe to receive twice. These paths have
local checks, but a real completed or failed mission still needs a player
playtest. The host saves its latest Shop result with the run transaction. After
a lobby disconnect, reconnect both launchers: the host replays a missed
victory, failure, or revival before syncing the current stage. The guest
applies the result once to its private run. Local checks cover this path;
two live games still need a full victory/failure/reconnect playtest.

A separate Shop map prototype now takes a host unit loadout and a guest unit
loadout. It creates distinct unit and weapon clones, gates each clone to one
player country, and assigns the guest an unused country from the same faction.
The launcher derives unit access, starting defenses, earned buildings and
powers, private starting credits, enemy scaling, production restrictions, and
unit buff stacks from each Shop run.
Both game copies generated identical Shop maps and reached gameplay in a local
direct launch. Grid Mode still uses its original shared country and clones.
The in-game sidebar gates, credit grants, AI buffs, and a full Shop co-op
victory need player tests. The
guest's different country may also change native subfaction tech or map
scripts, so each mission needs a playtest. Some unrelated Shop modifier effects
still follow the single-player map pipeline and need separate co-op work.

For a private diagnostic, save one active `shop_run.json` per player with the
same seed and stage. Start the host from its own game folder:

```sh
python RandomizerLauncher/tools/coop_direct.py \
  --game-root HOST_GAME --name CoopHost host-shop \
  --host-run HOST_SHOP_RUN.json --coop coop_sthunder
```

The guest starts from its own game folder:

```sh
python RandomizerLauncher/tools/coop_direct.py \
  --game-root GUEST_GAME --game-port 1235 --name CoopGuest join HOST_IP \
  --shop-run GUEST_SHOP_RUN.json
```

Use UDP 1234 on both computers; port 1235 is for two games on one PC. Use
separate Wine prefixes there. The guest sends its private reward snapshot,
plus seed and stage. The host rejects mismatched seed or
stage, builds one map containing both private loadouts, and sends that map
manifest to the guest. The guest checks its loadout before starting. Add
`--dry-run` before `host-shop` or `join` on both commands to verify pairing
without opening either game. This runs without `MentalOmegaClient.exe` but
does not advance either Shop run or synchronize buying and mission stages.
Check each player's in-game sidebar before relying on the private loadouts.

`tools/coop_prototype.py build-shop` remains available when both saved run
files are on one computer. It writes a map and manifest without connecting.

The launcher stage messages validate co-op offers, rerolls, selection,
commitment, matching seed/stage/completed missions, and reject changes after
commitment. The direct host/join diagnostic above remains useful for map tests
without changing either Shop run.

The remaining live checks are tracked in [TODOS.md](TODOS.md).

## ZeroTier connection

The player UI offers ZeroTier only. Previous LAN/Public IP settings migrate to
ZeroTier. It uses TCP `19420` for the persistent lobby, TCP `19421` for map
preparation and UDP `1234` for gameplay. There are no player-facing port controls.
A pairing code is required for every lobby connection; Host and Join retain
separate codes while the launcher is open. Closing the dialog preserves the
session. Disconnect after closing the game to change connection settings.

The connection log records connection stages and both peers' runtime hashes.
Text hashes normalize CRLF/LF; binary hashes remain exact. Version, native
multiplayer binaries, optional loose rules/art and co-op difficulty INIs are
checked before the lobby connects, along with native co-op catalogue rows.
Optional Phobos must match, including its
presence. Player saves/configuration and generated catalogue entries are excluded.
Selected source maps normalize text newlines and resolve filenames without
case sensitivity. Generated map bytes and spawn hashes must still match exactly.
Both players need the updated launcher protocol and fingerprint policy.

Use `tools/coop_local_test.py` to create two private copies, then verify pairing
and gameplay with both launchers. Compare exact `spawnmap.ini` bytes and their
SHA-256 against the launch handshake, and confirm matching game IDs and map
SHA-1 in the connection logs.
Shop production restrictions travel in each player's private loadout.
Live sidebar and UDP gameplay validation remain required.

## Two launchers on one Linux PC

Keep the main game closed. The helper below creates two private game copies
under `RandomizerLauncherData/coop_local/` and gives the guest its own Wine
prefix. It requires about 7 GB of disk. The command-line manifest is used
only to prepare and verify the two copies; the launcher UI generates and
launches the selected Grid map itself.

```sh
python RandomizerLauncher/tools/coop_prototype.py build --state RandomizerLauncherData/randomizer_coop_state.json --coop coop_sthunder --unit FV
python RandomizerLauncher/tools/coop_local_test.py prepare RandomizerLauncher/generated_coop/morcp_sthunder_<printed-id>.json
```

Open host and guest launchers in separate terminals:

```sh
python RandomizerLauncher/tools/coop_local_test.py launch RandomizerLauncher/generated_coop/morcp_sthunder_<printed-id>.json --player host
python RandomizerLauncher/tools/coop_local_test.py launch RandomizerLauncher/generated_coop/morcp_sthunder_<printed-id>.json --player guest
```

Use the ZeroTier connection dialog with host IP `127.0.0.1` for this
developer-only loopback diagnostic. Share the host pairing code with the guest.
The guest game UDP port becomes `1235` automatically. Loopback checks do not
verify a connection between two PCs.
Run `prepare` again to refresh both private executables and saved settings.
For an Arsenal seed, also pass `--source-mission COOP_STHUNDER` to the first
command when that map belongs to the generated mission order.

For Shop, use the same private host and guest game folders. Select Shop Mode,
check co-op in each **Shop Setup**, enter the same seed, and start separate Shop
runs. Each private folder saves its own `RandomizerLauncherData/shop_run.json`
and profile. Connect through **Co-op Connection…** and use the host's Shop
mission cards. The Grid manifest used by `prepare` only creates the private
copies; Shop launch generates its own map from current purchases.

## Production access and transport payloads

Archipelago uses the host's shared slot. The APWorld selects its separate co-op
mission snapshot from the exported `coop_mode` setting. Guest inventory mirrors
contain received-item indexes and check mappings; credentials and local AP
backups are excluded. Only the host queues AP checks or reports its goal.
Co-op map rewards and enemy effects come from the received-item ledger, rather
than local pre-generation reward assignments. AP events are deferred while a
mission snapshot is being prepared. See the shared-slot setup in
[COOP_CONNECTION_GUIDE.md](COOP_CONNECTION_GUIDE.md).

Co-op uses the saved run's earned access and starting roster. Standard keeps
each exact unit behind its faction's physical factory, including captured
factories. Chaos and Arsenal retain the shared current-faction production path.
Starting Standard roles resolve to the same faction/subfaction identities as
campaign starters. An empty starting roster grants no diagnostic IFV access.

Both human slots receive an invisible original-production gate through separate
Player @ A/B transfers. Native types retain their authored runtime ownership,
TechLevel, BuildLimit, positive prerequisites, placements, and TeamTypes. The
gate blocks their production in either human House, including after capture or
reverse engineering; earned units use their registered player clone instead.
No player ForbiddenHouses or factory-owner exclusions are added to native
actors. Enemy slots never receive the gate.

Sealed initial payloads have complete registered private definitions, with
production access disabled independently of the carrier's unlock. Super Thor
keeps five Guardian GIs, five Enforcers, and one Heavy Cruiser, including all
three weapons. Shop host and guest payloads use separate identities.

Generated-map markers changed, so both players must update their launcher and
prepare a fresh map. Existing seed progress can be kept. Static checks cover
all 36 maps; a two-PC gameplay test is still needed to verify capture menus,
scripted reinforcements, passenger firing, and synchronization in the engine.

## Diagnostic command line

`tools/coop_direct.py` still supports the earlier one-map diagnostic without
the launcher window. Use `--dry-run` on both peers to check pairing and game
files without starting Mental Omega.
