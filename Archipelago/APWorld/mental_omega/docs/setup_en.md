# Mental Omega Multiworld Setup Guide

1. Close Archipelago tools and copy this `.apworld` into Archipelago 0.6.8's
   `custom_worlds` folder.
2. Put Mental Omega Randomizer 1.42 in a separate, unmodified Mental Omega
   3.3.6 game root.
3. Choose the desired launcher settings. In its **Archipelago** tab, set the
   slot name, then choose **Save Player YAML**. No separate local seed or YAML
   load step is required.
4. Put that YAML in Archipelago's `Players` folder. Generate and host normally.
5. For an `archipelago.gg` room, keep **Server** as `archipelago.gg`, copy the
   game-server port shown on the room page, enter the matching slot name and
   optional password, then connect. Do not paste the browser room URL.

Alternatively, open Archipelago's **Options Creator**, select **Mental Omega**,
configure the grouped Randomizer options, enter the slot name, and select
**Export Options**. This creates the Player YAML without opening the Randomizer.

For co-op, enable **Co-op mode** before the host exports YAML, or select
**Co-op Missions** in Options Creator. Generate a new room using the matching
APWorld. Only the host connects to the shared AP slot; the guest joins through
the launcher's co-op connection dialog. Received items and progression are
shared. For Shop, both players start a local co-op run with the host's
AP-generated seed. Local Shop currencies and purchases remain private; the
host reports AP purchases, mission checks, and goal completion.

Launcher-exported `launcher_settings` records the exact visible launcher
controls. Options Creator YAML stores equivalent individual options. Archipelago
generates the full run from these settings for each room. After connection, AP seed, Grid,
mission availability, checked objectives, completion, progression, and unlocks
come from server state. Objective and victory checks synchronize automatically;
received items use the existing reward pipeline.

Saving YAML only prepares AP setup; standalone Unlocks remain visible until a
server connection validates. After validation, AP state/settings and every
affected launcher view come from the server. Disconnect restores the exact
standalone state/settings and refreshes those views; reconnect loads AP again.


## Required Grid victories and mission keys

New Grid rooms support exact required victory missions, generic consumable
mission keys, and mission-specific access items. Required Victory Missions
defaults to 1; Options Creator accepts `all` (numeric 0) for every generated
mission. Mission Unlock Mode defaults to Standard. Key Currency delivers one
shuffled Mission Key Supply worth the total board cost, allowing optional
purchases without permanently exhausting the required-objective budget. Its
protected bottom-right mission automatically gets a win requirement based on
the board size. Choose the unlock mode on the Archipelago page; hover over it
for an explanation. No separate currency setup is needed. Mission-Specific Keys opens only the mission
matching the received code. All keys grant access only; local gameplay victories
are still required. Install the matching updated launcher for slot-data version
8 and regenerate the room to use these settings.

See [Grid progression and mission access](grid_progression.md) for field names,
persistence, economy proof, compatibility, and manual gameplay checks.
