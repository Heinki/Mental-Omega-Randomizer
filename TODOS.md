## BUGS AND IMPROVEMENTS


### Co-op mode: live playtest remaining

Local host and guest games start. The shared Grid, co-op map pool, direct-IP
pairing setup, and provisional co-op Shop mission offers exist. Shop map
generation now creates country-gated host and guest unit clones; both local
game copies reached gameplay. A temporary game trigger confirmed the victory
marker appears in the real debug log. Shop Mode now exposes the co-op checkbox,
separate runs, host-controlled mission choices, and direct game launch. Local
Shop stage and pairing checks pass; a full co-op Shop mission still needs a
player playtest. The direct command-line diagnostic also exchanges private
unit loadouts and rejects mismatched seed or stage. Closing a Shop co-op game
without a host victory marker now records one failure on each player's private
run; host Emergency Revival decides whether both runs revive. Local failure and
duplicate-message checks pass.
Experimental co-op is disabled by a source constant in release builds; there
is no player-facing switch. LAN and ZeroTier share one connection choice. A
local TCP pairing diagnostic verifies identical Grid and Shop map bytes,
matching launch hashes and game IDs, and rejects a changed guest map. A host
Shop result is now stored in its run and replayed after lobby
reconnect; local victory, failure, revival, and duplicate checks pass.

- [ ] Play and win a full co-op mission; verify automatic host completion,
      guest sync, loss, disconnect, and replay behavior.
- [ ] Verify earned units and buffs in both live games, including build menus
      and synchronized combat.
- [x] Generate map-local earned powers and buildings, private Shop starting
      credits, enemy country and safe unit buffs, AI power grants, and private
      Shop unit/factory production restrictions. Grid credit rewards remain
      shared. Offline parity checks cover both map copies and all 36 maps.
      Confirm actual game effects in the two-player playtest; unit-tier buffs
      are conservatively skipped where native types may belong to a player.
- [x] Sync one host-controlled Shop stage: co-op mission offers, selection,
      commitment, rerolls, difficulty assist, and launch. Validated lobby
      snapshots, guest acknowledgement, separate run files, and UI flow exist.
- [x] Keep each player's Shop profile, Ore, purchases, buffs, and upgrades
      separate; exchange validated private reward snapshots from the launcher
      before launch.
- [ ] Enforce different host and guest loadouts in the same generated map;
      verify sidebar access and buffs in a live game. Country-gated clone
      generation and local game startup are implemented.
- [x] Apply host victory and close-without-victory failure to each Shop run
      separately. Host Emergency Revival controls both stage outcomes; repeat
      failure messages do not repeat the transaction. Local checks pass.
- [x] Recover a Shop result missed during lobby disconnect. The host stores
      its last result with the Shop transaction, then replays victory, failure,
      or revival on reconnect; local checks cover separate runs and duplicates.
      Full live-game verification remains in the first task.
- [x] Hide experimental co-op in release UI by default. A developer-only code
      constant controls test builds; saved player settings cannot enable it.
- [x] Combine LAN and ZeroTier into one connection choice; retain Public IP.
- [x] Verify local Grid and Shop pairing writes byte-identical maps and matching
      spawn metadata; reject a changed guest map before launch.
- [ ] Test two real PCs on LAN, ZeroTier, and forwarded public IPv4; package
      and document verified setups.

## INFO

To use Phobos add dll and edited ini
