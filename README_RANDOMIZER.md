# Mental Omega Randomizer User Guide

This is the authoritative player-facing guide for seed settings and reward behavior. Installation, building, and source layout are maintained in [README.md](README.md); implementation details are maintained in [TECHNICAL_FINDINGS.md](TECHNICAL_FINDINGS.md).

The launcher is currently standalone and offline. The option keys below are intentionally stable so they can later become Archipelago world options without redefining their meaning.

## Seed Lifecycle

- **Generate New Seed** replaces the active run, creates a new seed identifier, mission order, objective/victory checks, and complete reward plan.
- Seed-generation settings are copied into `randomizer_state.json`. Changing the Settings tab afterward affects the next seed, not the active seed.
- Difficulty and game speed are launch settings and may be changed between missions.
- The first three missions are open. Each completed mission opens one additional mission.
- The generated mission order contains **Missions to finish** missions, and the run finishes when all of those required victories are recorded.

## Settings Reference

### Main launcher settings

| UI setting | Standalone/AP option key | Values and default | What it changes | Timing |
|---|---|---|---|---|
| Seed | `seed` | Generated `MO-XXXXXXXX` identifier; blank config default | Seeds the deterministic mission order and reward plan. The **Generate New Seed** button creates a fresh identifier. | Seed generation |
| Campaign | `campaign_filter` | `All Campaigns`, `Allies`, `Soviets`, `Epsilon`, `Foehn`; default `All Campaigns` | Restricts the mission pool. In Standard mode it also selects the campaign-appropriate reward pool. Foehn Standard uses bundled Allied/Soviet roles because those campaigns operate those production families. | Seed generation |
| Missions to finish | `mission_goal` | `1` through the number of eligible missions; default `15` | Number of mission victories required to finish the run and therefore the length of the generated mission order. | Seed generation |
| Difficulty | `difficulty` | `Casual`, `Normal`, `Mental`; default `Normal` | Writes the selected campaign/human difficulty to launch configuration. It does not change rewards. | Every launch |
| Game speed | `game_speed` | `0 - Slowest` through `6 - Fastest`; default `3 - Medium` | Writes the engine speed and launches with `-SPEEDCONTROL`, keeping the in-game speed control available. It does not change rewards. | Every launch |
| Rewards per objective | `rewards_per_objective` | `1`–`10`; default `1` | Assigns exactly this many reward items to every briefing-objective check and to the separate Mission Victory check. Total mission rewards are `number of checks × this value`. | Seed generation |
| Buff allied helpers | `generation.buff_allied_helpers` | `false`/`true`; default `false` | Adds AI-controlled allied houses to friendly buff targets when map safety allows it. Additional player-controlled houses are always included without this option. Enemies are never intentionally included. | Seed generation |
| Reward mode | `generation.reward_mode` | `Standard`, `Chaos (Experimental)`; default `Standard` | Selects campaign-aware rewards or the all-faction Chaos production/access model described below. Chaos always enables access randomization. | Seed generation |

### Reward Pool settings

| UI setting | Standalone/AP option key | Default | What it changes |
|---|---|---:|---|
| Randomize unit access and lock unearned tech | `generation.randomize_unit_access` | `true` | Adds unit access rewards and removes unearned combat technology from player production. Economy essentials, MCVs, miners, and Engineers remain available. Chaos forces this on. |
| Include defensive building rewards | `generation.include_defensive_buildings` | `true` | Includes faction defenses in both access rewards and defense-targeted buffs. It does not randomize power plants, refineries, production structures, walls, or gates. |
| Include buff rewards | `generation.include_buff_rewards` | `true` | Adds positive repeatable upgrades. Turning it off disables the buff-type selections. A seed must have access rewards, buff rewards, or both enabled. |
| Share buffs with same-tier equivalent units (Chaos only) | `generation.share_chaos_role_buffs` | `false` | Makes a unit buff affect its curated cross-faction peers, such as GI, Conscript, Initiate, and Knightframe. It does not grant access by itself. Shared groups appear together in Unlocks. |
| Include building-free superweapon rewards | `generation.include_superweapon_rewards` | `true` | Adds Lightning Storm, Tactical Nuke, Psychic Dominator, and Great Tempest to eligible reward pools. An earned power is restored at the start of future missions without its normal superweapon building. |
| Enabled Buff Types | `generation.enabled_buff_types` | All listed types | Limits which buff families seed generation may assign. This option is ignored when **Include buff rewards** is off. |

### Buff type options

| Option ID | UI label | Effect per stack | Implementation scope |
|---|---|---|---|
| `production` | Production / construction speed | 15% faster production or construction | House/category scoped. Per-unit production rewards are omitted in Chaos where unsupported. |
| `cost` | Cost reduction | 20% cheaper | House/category scoped in Standard; unit-specific in Chaos. |
| `speed` | Movement speed | 10% faster | House/category scoped in Standard; unit-specific in Chaos. |
| `armor` | Armor | About 10% stronger effective durability | House/category scoped in Standard; unit-specific effective durability in Chaos. |
| `health` | Health | 15% more health | Direct unit type; applied only when enemy use of that global type is not detected. |
| `sight` | Vision | +1 sight | Direct unit type with the same safety guard. |
| `damage` | Damage | 15% more weapon damage | Direct weapon type with unit and shared-weapon safety guards. |
| `reload` | Unit fire rate | 10% shorter weapon reload | Direct weapon type with unit and shared-weapon safety guards. |
| `rof` | Army-wide fire rate | 10% faster player/allied weapon fire | House scoped. |
| `range` | Attack range | +0.5 weapon range | Direct weapon type with unit and shared-weapon safety guards. |
| `ammo` | Ammo | +1 ammo capacity | Direct unit type with the same safety guard. |
| `self_healing` | Self-healing | Enables self-healing | Direct unit type; one effective stack. |
| `cloak` | Cloaking | Enables cloaking | Direct unit type; one effective stack. |
| `sensors` | Sensors | Enables sensors with a unit-derived radius | Direct unit type; one effective stack. |
| `guard_range` | Auto-engagement range | +1 automatic engagement range | Direct unit type; does not increase weapon range. |
| `veteran` | Veteran start | Newly produced affected units start veteran | House scoped; one effective stack because the engine flag does not start units elite. |

Direct unit and weapon definitions are global to the map. If an enemy uses the same type, the launcher skips that unsafe direct change instead of buffing the enemy or registering expensive cloned combat types. House-scoped rewards still use isolated player/allied country copies.

### Non-UI configuration keys

These keys are runtime/developer controls and should not become normal Archipelago options without a design review.

| Key | Default | Purpose |
|---|---:|---|
| `generation.starting_unlocked_missions` | `3` | Persisted compatibility value; the current launcher opens three missions at seed start. |
| `generation.enabled_reward_types` | `[access, buff, superweapon]` | Derived compatibility list written from the three reward-pool toggles. |
| `generation.safe_player_country_buffs` | `true` | Enables the stable map-local country safety path. |
| `generation.allow_shared_country_buffs` | `false` | Developer override that may affect enemy houses sharing a country; keep disabled for normal play. |
| `generation.transient_rulesmo_buffs` | `false` | Experimental loose `rulesmo.ini` injection; disabled because loose rules files can destabilize launches/client checks. |
| `generation.experimental_house_buffs` | `false` | Older experimental country-clone route; the stable safe-country path is preferred. |
| `archipelago.*` | Disabled/blank | Reserved connection and slot fields. They currently do not connect to an Archipelago server. |

## Reward Modes

### Standard

Standard keeps the reward pool appropriate to the selected campaign. Single-faction campaigns translate earned roles when a mission gives the player a foreign barracks, factory, air command, or shipyard. For example, an earned basic-infantry role can provide the corresponding unit for a captured production family.

Foehn Standard uses Allied/Soviet bundled access and compatible shared buffs because Foehn missions commonly operate those technologies. Standard **All Campaigns** uses Allied, Soviet, and Epsilon rewards; the complete Foehn reward catalogue is reserved for Chaos.

### Chaos (Experimental)

Chaos draws access and buffs independently from all four factions. An earned unit can be produced from any matching production building that the current mission gives the player: barracks for infantry, factories for vehicles, air commands for aircraft, shipyards for naval units, and Construction Yards for defenses. Chaos does **not** grant foreign production buildings.

The sidebar groups earned production cameos into faction bands with the current player faction first. Same-tier buff sharing is optional and off by default.

## Seeing Exact Rewards

The reward count is a summary, not a mystery bundle:

- Hover an incomplete mission row to see every remaining check and every assigned reward name.
- Select a mission and open **Rewards** to see each objective/victory check, its completion state, its count, and the full reward-name list.
- Open **Unlocks** to see rewards already earned, grouped by faction/unit with installed cameo art and accumulated buff effects.
- The mission table `Rewards` fraction counts reward items, not checks. With 10 rewards per check, completing one check advances it by 10.

Reward assignments are generated and stored when the seed is created. Access rewards are unique within a seed; once access is planned for a unit, later eligible slots can provide repeatable buffs. Some buff types have stack caps.

Victory is its own reward check. When the victory marker is detected, the launcher also grants any objective checks that were missed by the log watcher, so a won mission cannot remain partially rewarded.

## Mission Launch and Progress

The launcher reads campaign metadata from `INI\BattleClient.ini`, prepares a loose generated copy of the selected map, and starts:

```text
Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG
```

The generated map contains the current tech locks/unlocks, safe rewards, and objective/victory marker actions. The launcher watches `debug\debug.log`, records each marker once, and removes the temporary root map when the spawned process exits. After detected victory it waits briefly, closes the spawned game process tree, and prevents continuation into the normal campaign flow.

For action codes, trigger selection, marker construction, ordering guarantees, cleanup, and known mismatches, see [Objective and Victory Hooks](TECHNICAL_FINDINGS.md#objective-and-victory-hooks).

## Saved Data

| Data | Source mode | Packaged mode |
|---|---|---|
| Config defaults | `RandomizerLauncher\config\mental_omega_randomizer.yaml` | `RandomizerLauncherData\config\mental_omega_randomizer.yaml` |
| Active seed/progress | `RandomizerLauncher\randomizer_state.json` | `RandomizerLauncherData\randomizer_state.json` |
| Logs, maps, backups, cameos | Under `RandomizerLauncher` | Under `RandomizerLauncherData` |

Configuration describes the next seed. State describes the active seed and must be preserved to continue that run.

## Player-Facing Limitations

- Objective text and map trigger actions do not always have a one-to-one relationship. Victory tracking is broader than objective tracking.
- Direct unit/weapon buffs can be skipped on maps where enemies share the affected global type.
- A matching constructed superweapon building may share the already granted power instead of creating a second independent cameo.
- Game-speed behavior still needs validation across more campaign maps.
- Archipelago connection fields are placeholders only.
