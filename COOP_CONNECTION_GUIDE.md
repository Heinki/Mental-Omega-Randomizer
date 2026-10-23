# Co-op connection guide

The launcher connects one host and one guest over an authorized private
ZeroTier or Tailscale network. Public-IP connections are outside the supported
setup. Network clients and memberships are managed separately from the launcher.
Cooperative campaign missions require two humans; challenges also offer
standalone play with an optional AI teammate. See the
[challenge guide](CHALLENGES_TESTING.md) for that local flow and supported modes.

## Connect two PCs

1. Keep an existing working private route, or install the official network
   client on both PCs. For ZeroTier, join the same private network and authorize
   both devices; see the [official setup guide](https://docs.zerotier.com/start/).
   For Tailscale, use two authorized devices on the same tailnet.
2. Use the same launcher version and matching clean Mental Omega installations.
   Each launcher needs its own game folder. In **Settings**, select mission
   category **coop**, or **challenge** with **Human players: 2**. Co-op controls
   are available in the main settings and Shop Setup where supported.
3. For Classic, Mission List, or Grid Mode, the host generates or continues the
   shared run. For ordinary co-op Shop Mode, both players first start separate
   runs with the same seed and stage; each retains their own profile and purchases.
   Use the same eligible mission pool, repeat/Endless rules, and mission-control
   modifiers (No Safety Net, Narrow Intelligence, Hardcore, Faction Roulette).
   Other supported modifiers and personal upgrades can differ.
   A guest joining a Shop host from another mode receives setup instructions.
   Start the matching guest run and reconnect. Existing active runs are preserved.
4. Open **Co-op Connection**. The host chooses **Host**, enters a player name,
   and clicks **Connect**. Share the displayed pairing code and private-network
   IPv4 privately. A host does not enter an address.
5. The guest chooses **Join**, enters a different player name, pastes the host's
   ZeroTier Managed IPv4 or Tailscale IPv4 and pairing code, then connects.
   Enter only the IPv4: no subnet suffix, port, URL, or network ID.
6. Wait for connected status. In challenges, each human chooses a house and color
   in the dialog; launch checks both against native map restrictions and requires
   distinct permitted colors. Houses are per-match choices and do not reset the run.
7. The host selects and launches a mission; the guest can suggest one. Both
   challenge games use the host's difficulty and pinned game speed. Keep both
   launchers connected through gameplay and result synchronization.

A shared standalone run mirrors unlocked units, buildings, buffs, and powers.
Each challenge human receives a roster for their chosen country. Earned powers
have separate native player providers, including Chronolift and Time Freeze.
Shop purchases stay private. Matching prepared maps and a working lobby do not
by themselves verify a live game session.

In Shop, the host selects an offer, waits for the guest acknowledgement, commits
it, then launches after the committed stage is acknowledged. The guest's mission
cards offer **Suggest Mission**; only the host changes mission controls. Personal
production-speed upgrades, Glass Cannon, Overclocked Factories, and Support
Doctrine apply to that player's generated units and powers. Demolition Charges,
Melee Fighters, and One Shot, One Kill are unavailable in co-op because their
campaign implementations rewrite native actors globally.

Progression mode remains locked while paired. To give up, reset a profile, start
a new run, or enter Endless, disconnect first. For Endless, both players must
start matching Endless runs before reconnecting. Close both games before changing
the next stage. Update both launchers for Shop stage schema 2 and map marker V5;
existing profiles and purchases are retained.

## Ports and optional Windows firewall helper

Final Fortress has its own **Co-op…** button in the Fortress header. The host
chooses two or three humans. Guests select different player numbers (2 or 3),
enter the host's ZeroTier IPv4 and pairing code, and use distinct names. The
host launches after the full roster connects. All human players share the host's
faction and enabled perks, but earn and spend Defensive Points in their own
profiles. Two humans allow at most one perk-enabled AI helper; three allow none.
Fortress uses TCP **19420** for guest 2 and TCP **19422** for guest 3, with UDP
**1234**, **1235**, and **1236** for human players 1–3. Every player must be able
to reach every other player on the private network. Mid-game joining is not
supported. Disconnect the Fortress lobby before switching modes.

For Grid/Shop/challenges, the automatic ports are host TCP **19420** for the lobby, host TCP **19421** for
map preparation, and UDP **1234** on both PCs for the game. Permit this traffic
over the intended private network. Router forwarding is not part of this setup.
See [ZeroTier firewall guidance](https://docs.zerotier.com/routertips/).

For Windows ZeroTier/Tailscale adapters, use the supplied
`Setup-Private-Network.ps1` beside the launcher EXE. A source build can copy it
from `tools/` into the game folder. Run it from that folder and preview before applying:

```powershell
.\Setup-Private-Network.ps1 -WhatIf
.\Setup-Private-Network.ps1 -Elevate
```

`-Elevate` requests Windows administrator approval. The helper scopes inbound
rules to this game folder's launcher and `gamemd.exe` on detected VPN adapters.
Use `-Launcher MentalOmegaRandomizer.exe` to select a particular EXE. Repeat
setup after moving the folder or changing the launcher filename. Setup failures
are reported in `Setup-Private-Network.log` beside the game.

## Archipelago with a shared ordinary co-op slot

Challenge seeds do not support Archipelago. For cooperative campaign missions,
select **coop** on the host before exporting its Player YAML, or enable
**Co-op Missions** in Archipelago's Options Creator. Install the matching APWorld,
create a room, and connect only the host launcher to that slot. Campaign rooms
retain their campaign mission pool.

The guest joins through Co-op Connection and does not open another AP connection.
Host victories report checks and the goal. Received units, buildings, buffs,
powers, and enemy Trap items mirror to the guest for subsequent prepared maps;
replayed item indexes do not duplicate rewards.

For ordinary co-op Shop, both local runs use the host's AP-generated Randomizer
seed. The matching guest run binds to shared AP inventory when joining. AP rewards
are shared; local Ore, profiles, and purchases remain private. Only the host spends
Mental Coins on generated AP purchase checks. Reconnection resends shared inventory
and stage progress. A hosted AP room with two-PC gameplay still needs a live test;
loopback protocol checks do not establish that coverage.

## Private fields, runtime checks, and diagnostics

The host pairing code is visible and noneditable. Each launcher retains its own
host code separately from the entered guest code while open. **Copy pairing code**
uses the selected role. Guest address/code fields are masked by default;
**Show IP and code (visible on stream)** temporarily reveals them. Closing the
dialog keeps the connection open. To change connection settings, close the game,
disconnect, and reconnect.

**Show connection log** displays synchronization and preparation failures;
**Copy connection log** copies it. Connection messages redact addresses and codes,
but native `spawn.ini`, game logs, and clipboard history can contain addresses.
Packaged launcher diagnostics are in `RandomizerLauncherData/logs/launcher.log`;
source launches use `RandomizerLauncher/logs/launcher.log`.

If **Mental Omega runtime differs** appears, compare the listed files. Connection
logs include normalized and raw SHA-256 values. Version files, co-op difficulty
INIs, and optional loose rules/art permit line-ending differences. Native binaries,
including optional Phobos, must match exactly; an optional file present on only
one PC also differs. Player saves and configuration are excluded. Selected native
maps use normalized source hashes and case-independent filenames, while prepared
maps must be byte-identical with matching spawn metadata. Native catalogue entries,
enemy positions, and player restrictions are checked; generated lobby rows are ignored.

Generated co-op maps suppress the cosmetic `BEHIND` animation after an observed
cross-client object-ID/checksum mismatch from hidden reward providers. Both peers
must update and reconnect to regenerate maps. This compatibility handling applies
to ordinary shared and Shop maps; sustained native gameplay still needs verification.
Old launcher protocols are rejected with an update message. Update both peers
together; keep their existing save folders.

For timeouts, check that both VPN devices are online and authorized, the guest has
the correct private IPv4 and pairing code, and the host log shows **Co-op lobby
listening on TCP 19420**. The guest retries refused connections and individual
socket timeouts for up to 30 seconds. Persistent blocked traffic needs a route
or local firewall correction.

While the host is listening, a Windows guest can check the lobby port:

```powershell
Test-NetConnection -ComputerName 'HOST_PRIVATE_IPV4' -Port 19420
```

`TcpTestSucceeded: False` means that port was unreachable. The probe does not
perform the launcher handshake, so the host may log a disconnect. Disconnect and
connect again on the host before retrying Join. See Microsoft's
[Test-NetConnection reference](https://learn.microsoft.com/en-us/powershell/module/nettcpip/test-netconnection).
If the lobby connects but preparation fails, check TCP **19421**. If both games
start but cannot communicate, check UDP **1234** on both PCs. Report the mission,
seed, platforms, connection log, and native game logs after reviewing private data.

Maintainer loopback checks can use `127.0.0.1` with separate game directories and,
when applicable, separate Wine prefixes. The guest then uses UDP **1235**
automatically. Do not share `spawn.ini`, `spawnmap.ini`, or runtime data between
instances. These checks do not verify Windows/Linux gameplay over a VPN.
