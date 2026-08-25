# Playing Mental Omega with Archipelago

This guide explains how to install Mental Omega Randomizer for Archipelago,
create a player YAML, connect to a room, and continue an existing game.

## What you need

- Mental Omega 3.3.6 in a separate, unmodified game installation
- Mental Omega Randomizer Launcher 1.30
- Archipelago 0.6.7
- `mental_omega.apworld` from the same Randomizer release as the launcher

Use matching launcher and APWorld releases. A YAML created by another
Randomizer version may be rejected when connecting.

## Install the Randomizer

1. Put `MentalOmegaRandomizer.exe` in the Mental Omega game folder.
2. Confirm that it is beside `MentalOmegaClient.exe`, `Syringe.exe`, and
   `gamemd.exe`.
3. Start `MentalOmegaRandomizer.exe`.

Use a separate Mental Omega installation for the Randomizer. Do not install it
over a game folder containing unrelated rule or map modifications.

## Install the APWorld

1. Close all Archipelago programs.
2. Copy `mental_omega.apworld` into Archipelago's `custom_worlds` folder.
3. Restart the Archipelago Launcher.

Every person who generates or hosts the room needs this APWorld installed.
Other players do not need Mental Omega unless they are playing the Mental
Omega slot.

## Create your player YAML

The launcher exports the YAML needed by Archipelago. It uses the exact values
currently visible on the Randomizer's **Settings** and **Advanced** pages.

1. Open the Randomizer launcher.
2. Choose the campaigns, progression mode, Grid options, rewards, difficulty,
   and other settings you want.
3. Open the **Archipelago** tab.
4. Enter the slot name that you will use in the room.
5. Select **Save Player YAML** and choose where to save the file.
6. Give the YAML to the room host, or place it in Archipelago's `Players`
   folder if you are generating the room yourself.

**Save Player YAML** both saves the current Archipelago settings and exports a
fresh player file. There is no YAML import step in the launcher. To change the
run, change the visible launcher settings and save a new YAML before generating
the Archipelago room.

`generated_world` is a normal Archipelago mapping option containing generated
mission order, Grid, reward slots, and compatibility checks required for this
exact run. Change launcher controls and save a new Player YAML instead of
editing generated data. Archipelago rejects mismatched readable settings.

## Mission progression and spheres

Archipelago logic uses one locked, local-only `Local Victory` marker for each
mission. These markers are never shuffled and never unlock missions inside the
launcher. The launcher still opens missions from its own persisted victories.
It reports the matching marker alongside each mission victory so the server's
logical record stays synchronized.

Mission List/Classic rules use the manifest's exact starting mission count and
victory-count requirements. Grid rules use the signed start nodes and exact
orthogonal neighbors from the generated topology. Consequently later mission
checks enter later logical spheres instead of every mission appearing in
Sphere 1. The local markers are visible in spoiler/playthrough output because
they are the explicit bridge between real local progress and Archipelago's
item-based sphere model.

After each validated connection, `logs/launcher.log` records one
`archipelago_expected_logic_spheres` event. It groups mission codes by their
earliest logic sphere, lists the starting missions, and records the expected
goal sphere. Mission-specific Archipelago diagnostic events also include an
`expected_logic_sphere` field. These values describe earliest reachability;
the generated spoiler playthrough may omit optional Grid branches that are not
required for the goal.

The normal Details tab shows compact counts for the connected seed: active
reward checks, checks whose placed item belongs to the local player, checks
whose item belongs to another player/world, and distinct potential rewards
allowed by the seed's frozen settings and mission-specific pools. Recipient
counts come from server scouting and can briefly show an awaiting-details
count while metadata arrives. Local-only victory logic markers are excluded.

Connection diagnostics also record `archipelago_reward_check_counts` with the
active check count, potential-reward count, and their difference. A negative
difference is logged at warning level. This is informational only and does not
change Archipelago generation or fill behavior.

## Generate and host the room

Generate the multiworld normally with Archipelago 0.6.7 after every player's
YAML is in the `Players` folder. Upload or host the generated output using your
normal Archipelago workflow.

Do not replace the Mental Omega YAML after the room has been generated. A new
YAML describes a new run and will not match the existing room.

## Connect the launcher

1. Open the room page and find its game-server port.
2. Open the Randomizer's **Archipelago** tab.
3. For an Archipelago-hosted room, leave **Server** as `archipelago.gg`.
4. Enter the game-server port from the room page.
5. Enter the exact slot name used in the YAML.
6. Enter the room password when one is required.
7. Select **Connect**.

Do not paste the browser room URL into the server field. Hosted rooms use the
bare `archipelago.gg` host plus the separate game-server port. The launcher
automatically uses a secure connection for hosted rooms. Custom and local
servers may use their own hostname and port.

TLS certificate verification and hostname checking remain enabled. If a
system reports `CERTIFICATE_VERIFY_FAILED`, check its clock and Windows trusted
roots, then check whether antivirus or a corporate proxy is intercepting TLS.
The launcher log records the endpoint, OpenSSL/Python versions, certificate
store counts and paths, proxy host (never credentials), and verification code
for a support report.

When validation succeeds, the connection status turns green. The launcher
then loads the seed, mission list, Grid, unlocks, completed checks, and
progression from the Archipelago server. Gameplay settings controlled by the
room become read-only while connected.

## Play and report checks

Launch missions through the Randomizer as usual. The launcher reports supported
mission objectives and mission victory to the server automatically. Items sent
to your slot enter the normal Randomizer unlock system and are applied when
generating missions.

The Archipelago activity feed shows player-facing server and item messages.
Item messages identify who found the item, its recipient, source location, and
game when the server provides that metadata. The chat field also accepts normal
chat and server commands such as `!hint` and `!release`.

In Grid Mode, the visible grid and mission availability come from the server.
Completing checks refreshes progression and unlock information. Finishing the
Grid goal follows the Grid completion option stored in the room's YAML.

In Shop Mode, use the launcher's **Shop Run** workspace. Its mission pool and
run length come from the signed room. Every victory reports the next private
stage marker and may report a shuffled mission-victory location. The
**AP Purchases** panel spends the displayed persistent Mental Coin price to
send one generated purchase location; Archipelago determines its item. Pending
purchases are retried after reconnecting without another debit. Finishing the
complete Shop run reports the slot goal. Each new run also rolls received AP
unit unlocks into remaining extra-unit slots, then reapplies every received
buff and power stack. This restart boost comes only from received AP items; it
does not alter mission credits, Ore, or Mental Coins. The generated YAML signs
this behavior as `received_unit_loadout: random` inside its Shop settings.

## Disconnect and continue later

Disconnecting switches the launcher back to the latest standalone Randomizer
state and settings. The mission views, Grid, and Unlocks page refresh to show
that local state.

Reconnect to the same room and slot to load the current Archipelago state
again. The server remains authoritative for AP checks, received items, mission
completion, and progression. Already reported checks are synchronized without
granting their rewards twice.

## Troubleshooting

### The launcher cannot connect

- Use `archipelago.gg`, not the browser room URL.
- Copy the room's game-server port exactly.
- Match the slot name exactly, including spaces and capitalization.
- Enter the room password if the host configured one.
- Confirm that the room is running and has not expired.

### Version or manifest mismatch

- Use the launcher and `mental_omega.apworld` from the same release.
- Generate the room with the APWorld installed.
- Use the YAML that generated this room, not a newer replacement YAML.
- If settings must change, save a new YAML and generate a new room.

### The wrong missions or unlocks are visible

- Confirm that connection status is green.
- Confirm that you connected to the intended room and slot.
- Disconnect to view standalone state; reconnect to restore AP state.

### A completed check has not appeared

- Keep the launcher running while playing the mission.
- Return to the launcher and confirm that it is still connected.
- Reconnect to request synchronization from the server.
- Check the activity feed for a server refusal or compatibility message.
