## BUGS AND IMPROVEMENTS
- V1.42, Chaos, Grid Mode
Great Tempest doesn't do damage
I think this has been mentioned before, but it’s still bugged though

Source fix implemented: the animation-warhead preload lowercased engine INI
keys, leaving the vortex damage radius at zero. Preserve key/type casing.
Isolated engine verification now loads radius 19 with damage 40 at maximum
buffs. Campaign-map audits pass. Restart the mission; old saves retain the
broken definitions. Confirm battlefield damage in gameplay.

## INFO

To use Phobos add dll and edited ini
