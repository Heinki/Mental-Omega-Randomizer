# Mental Omega Multiworld Setup Guide

1. Close Archipelago tools and copy this `.apworld` into Archipelago 0.6.7's
   `custom_worlds` folder.
2. Put Mental Omega Randomizer 1.24 in a separate, unmodified Mental Omega
   3.3.6 game root.
3. Generate the Randomizer seed. In its **Archipelago** tab, set the slot name,
   choose **Generate YAML**, then **Save YAML**.
4. Put that YAML in Archipelago's `Players` folder. Generate and host normally.
5. For an `archipelago.gg` room, keep **Server** as `archipelago.gg`, copy the
   game-server port shown on the room page, enter the matching slot name and
   optional password, then connect. Do not paste the browser room URL.

`launcher_settings` is readable and mirrors the launcher's normal nested YAML
settings. To customize it, edit that mapping, use **Load YAML** in the
launcher, generate a new seed, then generate/save the player YAML again. Do
not edit generated `run_manifest` data. Its checksum must exactly match the
selected launcher YAML and server slot. After connection, AP seed, Grid,
mission availability, checked objectives, completion, progression, and unlocks
come from server state. Objective and victory checks synchronize automatically;
received items use the existing reward pipeline.

Generating/loading YAML only prepares AP setup; standalone Unlocks remain
visible until a server connection validates. After validation, AP rewards stay
active through disconnects for offline safety and reconnection. Generate a new
seed to return to standalone mode.
