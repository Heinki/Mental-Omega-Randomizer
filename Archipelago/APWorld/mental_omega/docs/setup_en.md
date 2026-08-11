# Mental Omega Multiworld Setup Guide

1. Close Archipelago tools and copy this `.apworld` into Archipelago 0.6.7's
   `custom_worlds` folder.
2. Put Mental Omega Randomizer 1.26 in a separate, unmodified Mental Omega
   3.3.6 game root.
3. Choose the desired launcher settings. In its **Archipelago** tab, set the
   slot name, then choose **Save Player YAML**. No separate local seed or YAML
   load step is required.
4. Put that YAML in Archipelago's `Players` folder. Generate and host normally.
5. For an `archipelago.gg` room, keep **Server** as `archipelago.gg`, copy the
   game-server port shown on the room page, enter the matching slot name and
   optional password, then connect. Do not paste the browser room URL.

`launcher_settings` records the exact visible launcher controls. To customize
it, change those controls and choose **Save Player YAML** again. Do not edit
generated `run_manifest` data. Its checksum must exactly match the selected
launcher YAML and server slot. After connection, AP seed, Grid,
mission availability, checked objectives, completion, progression, and unlocks
come from server state. Objective and victory checks synchronize automatically;
received items use the existing reward pipeline.

Saving YAML only prepares AP setup; standalone Unlocks remain visible until a
server connection validates. After validation, AP state/settings and every
affected launcher view come from the server. Disconnect restores the exact
standalone state/settings and refreshes those views; reconnect loads AP again.
