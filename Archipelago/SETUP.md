# Mental Omega Archipelago Setup

## Required versions

- Mental Omega Randomizer Launcher 1.35
- Mental Omega 3.3.6 in a separate, unmodified installation
- Archipelago 0.6.7
- `mental_omega.apworld` from the same Randomizer release as the launcher

## Install

1. Close Archipelago tools.
2. Copy `mental_omega.apworld` into Archipelago's `custom_worlds` folder.
3. Put `MentalOmegaRandomizer.exe` in the Mental Omega game root beside
   `MentalOmegaClient.exe`, `Syringe.exe`, and `gamemd.exe`.
4. Start the launcher and choose the desired values on **Settings** and
   **Advanced**. A separate local seed is not required.
5. Open the **Archipelago** tab, enter the intended slot name, then choose
   **Save Player YAML**. This saves the visible controls as reusable settings.
6. Put that YAML in Archipelago's `Players` folder. Generate and host the room
   normally with Archipelago 0.6.7.
7. In the Randomizer's Archipelago tab, keep **Server** as
   `archipelago.gg`, copy the room page's game-server port, enter the matching
   slot name and optional password, then choose **Connect**. The browser room
   URL is not the game-server address. The launcher automatically uses secure
   WebSocket (`wss://`) for hosted `archipelago.gg` rooms.

After connection validation, use the chat field below the synchronization log
for normal chat or server commands such as `!hint` and `!release`. Messages use
the authenticated slot name; Archipelago does not permit a separate chat alias.

The player YAML contains a readable `launcher_settings` mapping copied from
the current launcher controls. To change it, change the launcher settings and
choose **Save Player YAML** again. Archipelago creates the mission order, Grid,
starters, rewards, and signed run manifest while generating the room.

The launcher refuses incompatible server state or reward/mission catalogues.
Saving YAML only stages AP setup, so the existing standalone reward plan and
Unlocks UI remain active until the server connection validates. A validated
connection switches state, settings, missions, Grid progress, and Unlocks to
the server-owned AP run. While connected, all gameplay-affecting settings are
read-only. Disconnecting restores the exact standalone state/settings and
refreshes every affected view; reconnecting loads the AP server state again.

Every participant generating or hosting the room needs the APWorld installed.
Only the Mental Omega player needs the game and Randomizer launcher.

## Shop Mode and YAML compatibility fixes

Replace the installed APWorld in Archipelago's `custom_worlds` folder with the
APWorld from this checkout, then restart Archipelago before generating. An
older installed APWorld keeps its old version checks even after the launcher
is updated. In particular, Mental Omega's `1.34` versus `1.33` error means the
installed APWorld is outdated.

Launcher release labels no longer reject an otherwise compatible run. Schema,
mission/reward catalogue, and manifest integrity checks still reject incompatible
or damaged input. The APWorld generates and signs a complete run from the
exported settings. Legacy manifest YAMLs are accepted and regenerated. Player
YAML uses JSON-compatible mappings to preserve setting types exactly. Re-export through **Save Player YAML** when
changing settings or replacing an incompatible catalogue.

For an AP Shop run, select **Shop Mode**, save the Player YAML, generate and host
the room, then connect the launcher. **Start Shop Mode** remains available after
connection validation and after a failed or completed run. Generation settings
remain locked while connected. AP purchases are scouted; stage victories are
sent as checks, and stage-marker receipts are acknowledged without becoming
ordinary Shop rewards. Only a completed run belonging to the current AP slot
can report its goal.

Run `tools/check_archipelago_integration.py --archipelago-root /path/to/Archipelago`
with Archipelago 0.6.7's Python environment to verify YAML, generation, item fill,
beatability, handshake, and Shop controls. Add `--apworld /path/to/game.apworld`
to test the packaged world.
