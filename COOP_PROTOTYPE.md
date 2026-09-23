# Direct co-op prototype

The randomizer hosts and joins directly. `MentalOmegaClient.exe` and the
CnCNet service are not used. The launcher shares run state over TCP, prepares
matching co-op maps on both computers, writes `spawn.ini` and `spawnmap.ini`,
then starts the game through `Syringe.exe`. The game uses UDP between players.

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
4. On the guest, check **Co-op mode (2 players)**. Open **Co-op Connection…**
   on both launchers. Host selects **Host** and **Connect**. Guest selects
   **Join**, enters host IP, and selects **Connect**. Use distinct player names.
5. Guest receives host's saved run and Grid. Both see the same map order,
   unlocks, rewards, and host-selected mission. A guest can click a map or use
   **Suggest Mission**; suggestion appears in host log and connection dialog.
   Host selects the playable map and clicks **Launch Selected Mission**. Both
   games start automatically after source-map and patch-version checks.

The lobby stays connected after the game closes. Host can mark a completed
co-op mission with **Mark Mission Complete**; the updated Grid and rewards sync
to guest. Automatic co-op victory detection is not implemented yet. Only host
can generate a seed, launch a game, or record completion. Guest's own saved
run remains untouched and returns after disconnecting.

Each player receives the same earned infantry, vehicle, aircraft, and naval
access plus supported earned unit buffs. Randomizer Arsenal uses the selected
co-op mission's arsenal. If no access is earned, a logged `FV` test grant lets
the first map launch. The prototype does not yet transfer earned powers,
building rewards, starting credits, enemy scaling, or every single-player
production gate. Native co-op map technology remains available. Shop Mode is
outside this prototype.

## Internet connection

ZeroTier is the recommended first test. Create one private ZeroTier network,
join and authorize both computers, and enter the host's ZeroTier managed IP
in the guest launcher. Test that the two devices can reach each other. Allow
incoming TCP `19420` (lobby) and TCP `19421` (game preparation) on the host,
plus UDP `1234` on both computers' system firewalls over the ZeroTier
interface. If using a
custom lobby port, allow that port and the next TCP port. ZeroTier normally
handles router traversal; router forwarding is not normally needed for its
virtual network. Direct public IP requires reachable TCP ports and UDP game
traffic through both routers/NATs and is less predictable.

See the [ZeroTier quickstart](https://docs.zerotier.com/quickstart/) and
[router/firewall guidance](https://docs.zerotier.com/routertips/).

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

Use host IP `127.0.0.1`. Guest game UDP port becomes `1235` automatically.
Run `prepare` again to refresh both private executables and saved settings.
For an Arsenal seed, also pass `--source-mission COOP_STHUNDER` to the first
command when that map belongs to the generated mission order.

## Diagnostic command line

`tools/coop_direct.py` still supports the earlier one-map diagnostic without
the launcher window. Use `--dry-run` on both peers to check pairing and game
files without starting Mental Omega.
