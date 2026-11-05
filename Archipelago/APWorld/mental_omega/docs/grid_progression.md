# Grid victory objectives and Archipelago mission access

## Settings

These settings affect Grid Mode only. Existing saves without `required_goals`
retain their original single bottom-right objective. Shop Mode and other
independent progression modes retain their existing rules.

| Launcher setting | Default | Launcher YAML field | Options Creator field |
| --- | --- | --- | --- |
| Required Victory Missions | `1` | `required_victory_missions` | `required_victory_missions` (`all` / `0` means All) |
| Archipelago Mission Unlock Mode | `Standard` | `mission_unlock_mode` | `mission_unlock_mode`: `standard`, `key_currency`, `mission_specific_keys` |
| Final-mission win requirement | Chosen automatically; no launcher control | Omitted; the APWorld chooses the balanced default | Advanced YAML override only; hidden in Options Creator |

Mission Unlock Mode is on the **Archipelago** page in **Grid Mission Access**,
with hover tooltips and an explanation that changes with the selected mode.
Selecting Key Currency automatically configures prices and the bottom-right
mission's win requirement; no separate currency or completion-gate setup is
needed. The launcher omits the completion-gate override from exported YAML;
the APWorld calculates it from the actual board. There is no editable `Auto` field.
Required Victory Missions remains in Settings because it also applies to
standalone Grid Mode, and its label and input both have explanatory tooltips.

Launcher-exported YAML stores these fields inside `launcher_settings`.
Options Creator exports the individual fields directly under the game's name.
`launcher_settings` remains authoritative when present; do not mix both styles
in the same player file. The server-generated manifest controls a connected
run. Changing local controls cannot change an existing room.

The required count accepts a positive integer or `All`. Integers larger than
the actual filtered/generated board are reduced to that board's mission count.
For `1`, the original bottom-right goal remains the only required mission.
For larger counts, exactly that many distinct mission codes are sampled from
the entire board. The bottom-right mission is not automatically included.
`All` requires every mission. A separate named deterministic RNG stream avoids
changing the existing mission order or reward RNG sequence.

Selected codes are frozen in `grid.required_goals`; the original `grid.goal`
continues to identify the physical bottom-right endgame mission. AP additionally
records the exact set in `goal.mission_codes`. Victory requires actual local
mission victories for every selected code. Neither completing other missions,
receiving items, buying access, nor server-released checks substitutes for this.
The release-all-rewards option runs only after the entire selected set is won.

Required missions retain their gold border and star in every status, including
locked and completed. Required locked tiles remain visible when other locked
tiles are hidden. The Grid footer shows progress and remaining objectives;
Details shows the complete remaining list. Tooltips explain access requirements.

## AP access modes

Standalone always uses its ordinary start nodes and orthogonal adjacency.
The AP-only controls prepare exported YAML; they do not activate keys locally.

**Standard** preserves the Grid's existing start nodes and adjacency rules.

**Mission-Specific Keys** gives every non-start mission its own progression
item, named `<stable mission code> Mission Key`. Only the matching mission
opens on receipt. Starting missions need no item. Keys are not spent, and
receiving one never completes its mission. Normal AP fill uses that exact key
as the mission region's rule, preventing self-locking placements and cycles.

**Key Currency** permits purchases anywhere on the board. A selected locked
mission shows its frozen cost; **Buy Mission Access** makes an atomic permanent
purchase for that seed. Prices range from 1 to 4 keys, with free starting
missions. Winning does not refund the price. The Grid shows received, starting,
spent, and available keys, and distinguishes missing currency from a completion
threshold and access that is affordable but not purchased yet.

### Currency safety and its deliberate tradeoff

Currency arrives as **one shuffled progression item, Mission Key Supply**.
Its frozen value equals the sum of every non-start mission's price. It may be
placed in any player's world by normal AP fill. It is not minted by the client,
precollected locally, or awarded by a mission victory outside AP delivery.

This is a whole-board budget, rather than a stream of separately placed coins.
After receiving it, all optional and required purchases are affordable in
aggregate, regardless of purchase order. Before receipt, free starting missions
provide real checks. Generation removes opening reward locks in key modes so
those checks remain available to AP fill. The supply cannot be placed behind
its own access rule by normal restrictive fill.

AP's cumulative item state can therefore model possession of the supply as a
logical permit for every paid region without assuming conflicting simultaneous
spends. The client still charges real keys separately for each purchase. Every
purchase reduces the unbought board cost by exactly its debit, so remaining
balance always covers all remaining prices. Optional spending cannot strand a
required mission. The tradeoff is a single large currency delivery: affordability
is not a staged progression curve after the supply arrives. Mission-specific
keys provide separately shuffled access progression when that is desired.

Keys replace an equal number of ordinary reward items in the existing real
location pool; they do not create fabricated checks. Existing reward/location
IDs and local-only victory markers stay stable. Generation rejects insufficient
reward capacity, missing starting checks, disconnected topology, invalid prices,
incorrect supply, and impossible completion thresholds. The signed manifest
contains prices, supply value, starting access, exact required goals, key IDs,
real reward capacity, and the protected mission/gate. The client validates that
contract before activation. No AP item-placement or gameplay execution was used
as validation during this implementation.

### Protected endgame mission

Only the physical bottom-right mission is protected in Currency mode, even
when it is not one of the randomly selected victory objectives. Other required
missions remain independent. If the bottom-right mission is also a starting
mission, no protected gate is applied.

`Auto` requires `floor(3*N/8)` prior completed missions, bounded by `N-1`.
An explicit threshold must be between `0` and `N-1`; invalid values reject room
generation with an explanatory error. The protected mission never counts toward
its own prerequisite. This gate counts distinct actual local mission victories,
not purchases, keys, or AP reward checks. All selected victory missions must
still be completed to finish the run.

## Persistence, IDs, and compatibility

New Grid rooms use `grid_contract: 2` and `slot_data_version: 8`. Use a matching
new launcher and APWorld, install the APWorld in `custom_worlds`, restart AP,
then generate a new room for these features. Older clients reject version 8
instead of silently applying adjacency or single-goal behavior. Existing rooms
and saves without the new contract keep their legacy defaults.

New IDs use reserved 48-bit game-specific namespaces: Mental Omega
`0x601000000000`, DTA `0x602000000000`, and Reloaded `0x603000000000`.
Mission keys use a deterministic SHA-256-derived 32-bit code suffix; the supply
uses offset `0x100000000`. ID collisions reject the catalogue. DTA's newly added
Grid-only local-victory markers use offset `0x200000000` plus the same code
suffix. Published item and location IDs are unchanged.

AP's immutable received-item checkpoint remains the receipt authority. Key
projection deduplicates item identity and never edits receipts to spend keys.
The separate `archipelago.mission_purchases` mapping records mission code and
frozen price. Purchase and receipt saves use atomic replacement and fsync.
Repeated clicks return without another charge. Failed saves restore the prior
in-memory purchase mapping. Restart/reconnect restores this mapping only when
the saved manifest, AP seed name, team, and slot match. Keep the launcher save
when moving computers: AP check history does not contain local purchases or
prove actual gameplay victories.

Server release/collect cannot finish new Grid missions. Local-only markers
mirror real victories for AP placement logic, but received markers never open
missions or count as local wins. DTA adds this bridge for new Grid rooms while
preserving its existing non-Grid/legacy behavior.

## Owner's manual gameplay checklist

- Generate standalone Grids with `1`, `3`, and `All`; verify default bottom-right
  behavior, exact marked objectives, irregular/filtered boards, and save reload.
- Complete an unselected mission and then only part of the selected set; verify
  no victory or release-all event occurs. Finish the entire selected set.
- Generate real AP rooms in all three access modes. Verify Options Creator and
  launcher YAML produce the intended settings and incompatible clients refuse.
- Deliver a mission-specific key from another player; verify only its matching
  mission opens and no victory is recorded. Reconnect and restart.
- Receive Mission Key Supply; buy nonadjacent missions, double-click purchase,
  restart, reconnect, and verify exact spent/remaining balance and access.
- Buy optional missions freely. Verify the remaining budget can still buy every
  remaining mission. Try the protected mission before/after its completion gate.
- Release/collect AP checks without playing missions; verify no local victory,
  threshold completion, or goal report. Finish every required mission normally.
- Connect to a different generated seed/team/slot; verify purchases and wins
  do not carry over. Verify existing legacy saves and ordinary non-Grid modes.

Gameplay remains for the owner to verify. No automated tests were added or run.
