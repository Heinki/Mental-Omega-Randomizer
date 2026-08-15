# Mental Omega Archipelago Setup

## Required versions

- Mental Omega Randomizer Launcher 1.27
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
   **Save Player YAML**. This generates the AP run from the visible controls
   and saves it in one operation.
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
choose **Save Player YAML** again. `generated_world` is checksum-protected
APWorld input. Archipelago generation rejects readable settings that no longer
match it, preventing silent configuration drift.

The launcher refuses incompatible server state or reward/mission catalogues.
Saving YAML only stages AP setup, so the existing standalone reward plan and
Unlocks UI remain active until the server connection validates. A validated
connection switches state, settings, missions, Grid progress, and Unlocks to
the server-owned AP run. While connected, all gameplay-affecting settings are
read-only. Disconnecting restores the exact standalone state/settings and
refreshes every affected view; reconnecting loads the AP server state again.

Every participant generating or hosting the room needs the APWorld installed.
Only the Mental Omega player needs the game and Randomizer launcher.
