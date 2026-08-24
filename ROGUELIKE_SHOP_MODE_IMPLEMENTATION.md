# Roguelike Shop Mode — Codex Implementation Specification

> Repository: `Heinki/Mental-Omega-Randomizer`
>
> Proposed file location: repository root as `ROGUELIKE_SHOP_MODE_IMPLEMENTATION.md`
>
> Status: implementation specification
>
> Primary goal: add a new **Shop / Roguelike Mode** with a 10-mission run, three mission choices per stage, run-based purchases, permanent meta progression, mission rerolls, difficulty modifiers, and full Archipelago compatibility.

---

## 1. Codex instruction

Implement this feature incrementally and keep the existing Classic, Mission List, Grid Mode, Randomizer Arsenal, buff, superpower, superweapon, Tier 1 starter, map-generation, objective tracking, failure tracking, and Archipelago behavior working.

Do **not** implement the whole feature inside `launcher_gui.py`, `randomizer/application/app.py`, or one oversized controller.

Follow the existing architecture:

- pure game rules belong in narrow modules under `randomizer/`
- UI composition belongs in `randomizer/application/` and `randomizer/ui/`
- persistence must use `randomizer/core/storage.py`
- existing reward definitions / reward canonicalization should be reused wherever possible
- mission access and Tier 1 starter logic must be reused instead of duplicated
- Archipelago network/session code must stay separated from local roguelike rules
- deterministic random decisions need named RNG streams and must not change existing RNG call order for other modes
- preserve all existing serialized IDs and compatibility behavior

This document is the source of truth for the new mode unless a repository invariant or existing compatibility rule requires a narrower implementation.

---

# 2. Feature name and terminology

Use the working progression mode name:

`Shop Mode`

Alternative display text may be:

`Roguelike Shop`

Internally prefer stable names such as:

- `SHOP_MODE`
- `shop_mode`
- `roguelike`
- `run_state`
- `meta_progression`
- `run_coins`
- `meta_coins`

Do not use ambiguous names such as only `money`, `cash`, or `coins` in persisted structures without specifying whether it belongs to the current run or permanent progression.

There are **two currencies**:

### Ore Coins

Temporary currency earned during the current 10-mission run.

Used to buy:

- unit access for this run
- buffs for units already owned in this run
- eligible powers / superweapons if enabled for Shop Mode
- temporary run modifiers
- mission rerolls if a run-based reroll price is configured

Ore Coins are reset when a new run starts.

### Mental Coins

Permanent account/profile currency.

Mental Coins persist across runs.

Used to buy:

- permanent unit unlocks
- permanent reroll upgrades
- permanent bonus Ore Coins per victory
- additional meta progression modifiers
- other permanent upgrades described later

Mental Coins are **not lost on run failure**.

---

# 3. Core game loop

A Shop Mode run consists of exactly **10 successful missions** by default.

The run sequence is:

1. Start a new run.
2. Load permanent/meta profile.
3. Build the player's eligible permanent unlock pool.
4. Apply mandatory starting Tier 1 access using the existing Tier 1 system.
5. Let the player select up to **5 extra permanent-unlocked units** for the run.
6. Initialize Ore Coins and permanent modifiers.
7. Generate three mission offers for mission slot 1.
8. Player may use available rerolls.
9. Player chooses one mission.
10. Open/use the Shop tab before launch.
11. Player purchases units and buffs.
12. Launch selected mission.
13. If victory:
    - mark the mission slot complete
    - award Ore Coins based on mission difficulty/class
    - award Mental Coins according to configured policy
    - apply permanent victory coin bonus
    - process Archipelago checks/items if connected
    - generate the next set of three mission offers
14. If failure:
    - the current run ends immediately
    - no further mission may be launched from that run
    - preserve permanent/meta profile
    - preserve AP-received permanent entitlements
    - display Run Over summary
    - require New Run / Restart Run
15. After victory 10:
    - mark the run completed
    - display Run Victory summary
    - award any finale/run-completion bonus
    - persist meta rewards
    - if this is an Archipelago goal condition, send goal completion exactly once
    - allow starting another run

The final mission is still one of the offered/chosen missions unless later balancing defines a dedicated finale pool.

The implementation must support replacing the default `10` with a future config value without rewriting the state model.

---

# 4. Mission choice system

Each run stage presents **three missions** to the player.

The player chooses exactly one.

The other two are discarded when the chosen mission is launched or committed.

## 4.1 Mission classes / difficulty

Every mission available to Shop Mode must have a normalized difficulty/economy class.

Initial classes:

- `act_1`
- `act_2`
- `operation`
- `finale`

If the existing mission metadata already provides a more precise classification, write one adapter that maps current repository classification into these four economy classes.

Do not scatter mission-code checks through Shop Mode.

Prefer data in `configs/missions.json` or another focused config if classification cannot be inferred safely.

Suggested default economy ranking:

| Class     | Relative difficulty | Default Run Coin reward | Default Meta Coin reward |
| --------- | ------------------: | ----------------------: | -----------------------: |
| Act 1     |                   1 |                       3 |                        1 |
| Act 2     |                   2 |                       5 |                        2 |
| Operation |                   3 |                       7 |                        3 |
| Finale    |                   4 |                      10 |                        4 |

These are **initial balance values only** and must be configurable.

Do not hardcode them into UI code.

Suggested config:

```json
{
  "shop_mode": {
    "run_length": 10,
    "mission_offer_count": 3,
    "mission_rewards": {
      "act_1": { "run_coins": 3, "meta_coins": 1 },
      "act_2": { "run_coins": 5, "meta_coins": 2 },
      "operation": { "run_coins": 7, "meta_coins": 3 },
      "finale": { "run_coins": 10, "meta_coins": 4 }
    }
  }
}
```

## 4.2 Offer variety

Use stage-based weights so later stages trend harder. A zero weight is a hard
exclusion, including during rerolls.

Implemented ten-stage profile:

- stages 1–2: Act 1 only, with one fixed-unit/hero offer when available
- stages 3–4: Act 1 / Act 2
- stages 5–6: Act 1 / Act 2 / Operation
- stages 7–8: Act 1 / Act 2 / Operation, weighted toward harder missions
- stage 9: Act 2 / Operation / Finale
- stage 10: Act 2 / Operation / Finale, strongly favor Finale

Do not make mission 10 impossible to generate because all finale missions were previously consumed.

The mission offer generator must handle exhausted pools safely.

## 4.3 Repeats

Default rule:

- do not offer a mission already successfully completed during the same run
- avoid duplicate missions within the same three-card offer
- after reroll, avoid reproducing the exact same three-card set when alternatives exist

Whether missions may repeat across **different runs** is unrestricted.

## 4.4 Mission RNG

Use a named RNG stream dedicated to Shop Mode mission offers, for example:

`shop_mission_offers`

Rerolls must be deterministic from the run seed + reroll count + stage or from a saved RNG state/derived stable seed.

Never change existing Classic/Grid/Mission List randomization output because Shop Mode was added.

Persist the generated current offer so reopening the launcher does not silently reroll it.

---

# 5. Run failure and run completion

A mission failure is fatal to the run.

After failure:

- set `status = "failed"`
- store `failed_mission_code`
- store `failed_stage`
- store a timestamp only if timestamps are already acceptable in persistence; do not use timestamps for deterministic logic
- disable Launch for the failed run
- disable purchasing with Ore Coins
- preserve the run summary for display
- do not delete the run immediately
- offer a clear `Start New Run` action

Any existing mission failure detection should be reused.

Do not create a second independent game-log parser just for Shop Mode.

A completed run uses:

`status = "completed"`

After stage 10 victory:

- stop generating offers
- preserve final run summary
- grant run completion rewards exactly once
- persist all permanent currency before presenting the completion UI

Both failure and completion need idempotency guards.

Repeated log parsing, launcher reopening, or AP reconnect must not pay mission rewards twice.

---

# 6. Shop inventory

The Shop is run-local and visible as part of the Shop Mode tab.

The player uses Ore Coins to buy access and buffs.

## 6.1 Unit purchases

Units have a Shop Mode run purchase price.

Unit purchase grants access for the remainder of the current run.

A purchased unit:

- is active in future mission launches in the run
- can receive Shop Mode buffs
- is not permanently unlocked unless separately purchased in Meta Progression
- must use existing access reward logic rather than a new parallel map patch system

Use existing reward catalogue entries as the canonical unit identity wherever possible.

Suggested run prices:

| Unit tier | Default Run Coin price |
| --------- | ---------------------: |
| Tier 1    |                      3 |
| Tier 2    |                      6 |
| Tier 3    |                     10 |

These values must be configurable.

Tier classification should use the repository's existing reward/unit classification where available.

## 6.2 Buff purchases

A buff may only be bought if the player currently has access to the corresponding unit.

Access can come from:

- mandatory Tier 1 starter system
- one of the player's selected permanent extra units
- a run unit purchase
- an Archipelago-received unlock
- another existing reward source explicitly considered active in Shop Mode

**Important:** owning a buff does not grant unit access.

Reuse the existing invariant that buffs and access are separate.

The Shop UI must filter or disable buffs for units that are not currently owned.

Recommended UX:

- purchased/owned unit: show eligible buffs
- not-owned unit: show unit card but buffs locked with tooltip `Purchase/unlock this unit first`
- maxed buff: show `MAX`
- insufficient Ore Coins: disable purchase

Existing buff stack limits remain authoritative.

Do not allow Shop Mode to exceed existing buff caps.

## 6.3 Power and superweapon support

The user specifically wants Shop Mode to work with the existing superpower/superweapon/unit buff systems.

Architect the Shop catalogue generically enough to support:

- unit access
- unit buff
- power access
- power buff
- superweapon access/buff if represented separately

If some reward categories are unsafe or nonsensical for Shop Mode, filter them in a dedicated eligibility rule rather than special-casing buttons.

---

# 7. Permanent meta progression

Add a permanent profile independent from a seed/run.

Suggested file:

`shop_profile.json`

Use the application data directory already used for launcher state rather than the game installation's source folders if the repository has a standard app-data location.

All writes must use atomic persistence through `randomizer/core/storage.py`.

Suggested schema:

```json
{
  "schema_version": 1,
  "meta_coins": 0,
  "lifetime_meta_coins_earned": 0,
  "lifetime_runs_started": 0,
  "lifetime_runs_completed": 0,
  "lifetime_missions_completed": 0,
  "permanent_unit_unlocks": [],
  "permanent_upgrades": {
    "mission_reroll_level": 0,
    "victory_run_coin_bonus_level": 0
  },
  "archipelago_profiles": {}
}
```

Do not rely on the statistics fields for gameplay.

Gameplay must depend only on canonical purchased unlock/upgrades and balances.

## 7.1 Permanent unit unlocks

Permanent unit unlocks are purchased with Mental Coins.

Once purchased, they stay available for selection at the start of future runs.

They do not automatically all become active in a run.

At new-run setup, the player may choose **up to 5 extra units** from their permanent unlock pool.

Mandatory starting Tier 1 units are separate and do not consume those 5 slots.

AP-received unit entitlements may either:

- join the selectable permanent pool, or
- be auto-active

Use one consistent rule. The preferred rule is described in the Archipelago section: AP unit unlocks join the entitlement pool and may be selected without paying Mental Coins.

## 7.2 Permanent unit prices

Default Meta Coin price by tier:

| Tier   | Permanent price |
| ------ | --------------: |
| Tier 1 |              10 |
| Tier 2 |              25 |
| Tier 3 |              50 |

These are initial tuning values and must be data/config driven.

Tier 3 must clearly cost more than Tier 2, and Tier 2 more than Tier 1.

Do not derive permanent prices from UI text.

## 7.3 Starting loadout

On `Start New Run`, show a loadout selection panel.

Always include existing mandatory Tier 1 starter access.

Then allow the player to select up to `5` extra units from:

- locally purchased permanent unit unlocks
- AP-received permanent unit entitlements for this AP slot/session identity

Rules:

- duplicate/equivalent access should not consume multiple slots if it resolves to the same canonical reward
- starter Tier 1 units already provided by the base starter system should not need to be selected
- selected extras are fixed once the run starts
- run purchases can add additional units later and do not count against the 5-starting-extra limit

The limit should be configurable as:

`max_selected_permanent_units = 5`

---

# 8. Permanent upgrades

Permanent upgrades are meta purchases, not ordinary unit buffs.

They should be modeled as stable IDs with levels, maximum levels, prices, and effects.

Suggested definitions:

```python
PermanentUpgrade(
    id="mission_reroll",
    max_level=3,
    ...
)

PermanentUpgrade(
    id="victory_run_coin_bonus",
    max_level=5,
    ...
)
```

Do not encode the upgrade definitions directly in button callbacks.

## 8.1 Mission reroll upgrade

Permanent upgrade:

`Mission Reroll`

Effect:

- grants reroll capacity for mission offers
- each reroll replaces all three current mission offers by default
- reroll cannot change a mission after it was launched
- rerolls refresh/reset according to configured policy

Recommended first implementation:

| Level | Effect            |
| ----: | ----------------- |
|     0 | no free rerolls   |
|     1 | 1 reroll per run  |
|     2 | 2 rerolls per run |
|     3 | 3 rerolls per run |

Alternative future balancing can make it `per stage`, but do not implement both policies at once.

Persist:

- permanent reroll level in meta profile
- `rerolls_used` in current run

The UI must display:

`Rerolls: 1 / 2`

Rerolling must save the new offer immediately.

## 8.2 Victory Run Coin bonus

Permanent upgrade:

`Victory Coin Bonus`

Maximum level: 5.

Effect:

`+1 Run Coin per successful mission per level`

Therefore:

- level 0: +0
- level 1: +1
- ...
- level 5: +5

This bonus is added after base mission-class Ore Coins.

Example:

Operation reward = 7  
Victory Coin Bonus level = 3  
Ore Coins awarded = 10

Display the breakdown in the victory result:

`Operation: +7`  
`Permanent Victory Bonus: +3`  
`Total: +10 Ore Coins`

This upgrade must never award money on a failed mission.

## 8.3 Suggested additional permanent upgrades

Build the system generically and optionally seed it with a small number of additional upgrades.

Good candidates:

### Starting Capital

+2 starting Ore Coins per level.

Max 5.

### Shop Discount

Reduce run-shop prices by 3% per level.

Max 5.

Apply discount at price calculation time and clamp final costs to at least 1.

### Extra Shop Choice

If the Shop later rotates inventory instead of showing the full catalogue, increase offered shop cards.

Do not implement unless the first Shop uses rotating offers.

### Second Chance

This is potentially powerful and conflicts with the core "one failure ends the run" identity.

Do **not** include in version 1.

If added later, make it expensive and explicit.

---

# 9. Difficulty / challenge modifiers

Add a run modifier system inspired by roguelite difficulty modifiers.

These modifiers should make runs easier or harder and may alter rewards.

The first implementation should use a small, explicit modifier catalogue instead of fully procedural effects.

Example modifiers:

### Greedy

`+25% Mental Coins earned, -2 starting Ore Coins`

### Veteran Economy

`Shop unit prices +20%, mission Run Coin rewards +30%`

### Poor Logistics

`Run Shop prices +2 flat`

### Generous Command

`+5 starting Ore Coins, -20% Meta Coin earnings`

### Blind Choice

`Mission offer hides one mission's exact reward until selected`

Only implement modifiers that can be represented safely by launcher logic.

Do not patch arbitrary combat values in version 1 unless reusing the existing buff system.

## 9.1 Modifier selection

Provide a section in the Shop Mode new-run setup:

`Run Modifiers`

Default: none.

The player can opt into modifiers.

Persist the selected modifiers into the run state so reopening does not change them.

Modifiers can use a reward multiplier:

`meta_reward_multiplier`

and/or direct effect hooks.

Clamp final currency rewards to non-negative integers.

---

# 10. UI requirement: its own tab

This is mandatory.

When `Shop Mode` is selected, its full gameplay UI must be shown in its **own workspace tab**, in the same application window where Grid Mode / Mission List content is currently displayed.

Do not open a separate top-level window for the primary Shop Mode experience.

Recommended tab title:

`Shop Run`

Suggested workspace tabs while Shop Mode is active:

- `Shop Run`
- existing `Settings`
- existing `Unlocks` or equivalent, if currently globally available
- `Archipelago` if connected / existing AP UI requires it

The `Shop Run` tab contains everything needed to play the mode.

## 10.1 Shop Run tab layout

Recommended vertical structure:

### Header

Show:

- `Run 4 / 10`
- Run status: `Active`, `Failed`, `Completed`
- `Ore Coins: 14`
- `Mental Coins: 37`
- `Rerolls: 1 / 2`
- AP connection badge when applicable

### Mission Choices

Three mission cards side by side when width allows.

Each card:

- mission name
- faction/campaign
- class: Act 1 / Act 2 / Operation / Finale
- displayed difficulty
- base Run Coin reward
- base Meta Coin reward
- modifier-adjusted estimated reward
- `Select` button

Selected mission is clearly highlighted.

Buttons:

- `Reroll Missions`
- `Launch Selected Mission`

### Run Shop

Sections/tabs/filter controls:

- Units
- Unit Buffs
- Powers
- Power Buffs

Cards show:

- cameo/icon
- name
- tier
- current state
- price
- purchase button

Unit card states:

- Starter
- Permanent Selected
- AP Entitlement
- Purchased This Run
- Available — X coins
- Locked from permanent pool but purchasable this run (if allowed by design)
- Unavailable for current campaign/arsenal

### Current Loadout

Show active access for this run:

- starter units
- selected permanent units
- AP-provided units
- run-purchased units
- purchased buffs

### Run History

Show stages completed:

`1. Allied Mission — Act 1 — +3/+1`  
`2. Soviet Mission — Act 2 — +5/+1`

Do not require navigating away from the Shop tab to understand the run.

## 10.2 Meta Shop UI

The same Shop Mode tab should include a clear section or nested internal panel:

`Permanent Unlocks`

This is available between runs and may optionally remain view-only during an active run.

Contains:

- Meta Coin balance
- permanent unit catalogue
- permanent upgrade catalogue
- purchased status
- tier
- price
- loadout selection when starting a new run

Preferred interaction:

- permanent purchases allowed while no active run exists
- during an active run, permanent shop remains visible but purchases are disabled or queued until next run

This avoids changing starting entitlements halfway through a run.

---

# 11. Persistence architecture

Persistence is the highest-risk part of this feature.

Separate these files/concepts:

## 11.1 Permanent profile

Example:

`shop_profile.json`

Contains permanent/meta progression only.

Never reset automatically on new seed or new run.

## 11.2 Current run

Example:

`shop_run.json`

Contains the currently active/failed/completed run.

Suggested schema:

```json
{
  "schema_version": 1,
  "run_id": "uuid",
  "seed": "stable seed",
  "status": "active",
  "stage": 3,
  "run_length": 10,
  "run_coins": 11,
  "rerolls_used": 1,
  "selected_permanent_units": ["GI Access", "Grizzly Tank Access"],
  "ap_entitlements_snapshot": [],
  "run_purchases": [{ "reward_id": "...", "quantity": 1 }],
  "run_buffs": [{ "reward_id": "...", "stacks": 2 }],
  "mission_offers": [
    { "mission_code": "...", "class": "act_1" },
    { "mission_code": "...", "class": "act_2" },
    { "mission_code": "...", "class": "operation" }
  ],
  "selected_mission_code": null,
  "completed_missions": [],
  "rewarded_victories": [],
  "modifiers": []
}
```

Use canonical reward IDs/names according to current repository conventions.

Do not save entire duplicate reward dictionaries if canonical IDs already exist.

## 11.3 Transaction safety

A mission victory has multiple side effects:

- mark victory
- add Ore Coins
- add Mental Coins
- mark idempotency key
- AP check
- generate next offers

Local persistence must be ordered so a crash cannot easily duplicate rewards.

Recommended local sequence:

1. detect mission victory
2. verify victory idempotency key is not already processed
3. calculate reward result
4. update in-memory run + meta profile
5. add the victory key to `rewarded_victories`
6. atomic-write permanent profile
7. atomic-write run state
8. send/queue AP check
9. generate next offers if not already generated
10. atomic-write updated run state

A stronger journal/transaction abstraction is welcome if it stays simple.

The critical rule is:

**A repeated victory event must not award currency twice.**

Use a stable idempotency key such as:

`{run_id}:{stage}:{mission_code}:victory`

Do not use only mission code because a mission can appear in another run.

---

# 12. Economy calculation module

Create a pure module, suggested:

`randomizer/shop/economy.py`

Functions should be testable without Tk.

Example API:

```python
def mission_reward(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    config=None,
) -> CurrencyReward:
    ...

def run_unit_price(reward, *, modifiers=(), upgrades=None, config=None) -> int:
    ...

def permanent_unit_price(reward, *, config=None) -> int:
    ...

def permanent_upgrade_price(upgrade_id, next_level, *, config=None) -> int:
    ...
```

Use a small immutable structure/dataclass for currency results.

All UI strings should be derived from returned values rather than recomputing economy logic.

---

# 13. Suggested module layout

Create a focused subsystem.

```text
randomizer/
  shop/
    __init__.py
    model.py
    economy.py
    missions.py
    catalogue.py
    purchases.py
    meta.py
    state.py
    modifiers.py
```

Suggested responsibilities:

### `model.py`

Dataclasses/enums/constants only.

Examples:

- `MissionOffer`
- `ShopRun`
- `ShopProfile`
- `CurrencyReward`
- `RunStatus`
- `MissionEconomyClass`
- `PermanentUpgradeDefinition`

### `economy.py`

All prices and coin reward calculations.

### `missions.py`

- mission classification adapter
- offer generation
- stage weights
- reroll generation
- duplicate filtering

### `catalogue.py`

Build Shop-eligible rewards from existing reward catalogue.

Do not redefine units/buffs.

### `purchases.py`

Pure purchase validation and state mutation helpers:

- can afford
- already owned
- buff requires access
- stack cap
- apply unit purchase
- apply buff purchase

### `meta.py`

Permanent unlock and upgrade rules.

### `state.py`

Normalization and migration of Shop Mode persisted structures.

### `modifiers.py`

Run-modifier definitions and effect application.

UI orchestration suggestion:

```text
randomizer/application/
  shop_controller.py
  shop_view.py
```

If the existing UI architecture prefers view-building in `randomizer/ui/`, place widget construction there and keep controller logic narrow.

---

# 14. Reuse existing reward system

The Shop must treat existing rewards as canonical content.

Do not create a second list such as:

```python
SHOP_UNITS = [...]
SHOP_BUFFS = [...]
```

unless it only stores Shop-specific metadata keyed by existing canonical IDs.

The Shop catalogue should adapt `REWARD_POOL` / current stable reward facade.

The current system already distinguishes reward kinds and buff access rules.

Maintain that separation.

For Shop purchases:

- unit access purchase -> canonical existing access reward
- buff purchase -> canonical existing buff reward
- power access -> canonical existing power reward
- power buff -> canonical existing power buff

When launching a mission, combine:

- normal Tier 1 starter access
- selected permanent Shop Mode access
- AP access
- run-purchased access
- run-purchased buffs
- AP buffs/items
- any other explicitly compatible active rewards

Then pass the resulting canonical reward set through the **existing** map pipeline.

---

# 15. Tier 1 starting units

The existing Tier 1 system is authoritative.

Do not replace it.

Shop Mode must start with the same baseline Tier 1 units that the existing randomizer already provides for the selected faction/families/mode.

The permanent selection of 5 extra units is added **on top** of those starters.

Tier 1 permanent unlocks can still exist in the meta shop if there are Tier 1 units outside the mandatory starter set or useful variant/equivalent unlocks.

When a permanent selection duplicates starter access, the UI should mark it as redundant and not consume a slot.

---

# 16. Archipelago integration

Shop Mode must work in:

1. normal standalone mode
2. Archipelago-connected mode

The design principle:

**The local 10-mission run is disposable. Archipelago progression is not.**

This is similar to roguelike Archipelago clients where death may reset the current run, but reconnecting restores items already earned in the multiworld.

## 16.1 AP-received items

When the AP server sends a unit/buff/power unlock:

- record it through the existing received-item ledger
- it must remain available after local Shop Mode run failure
- it must be reapplied after reconnect/restart
- receiving the same indexed AP item must not duplicate side effects beyond the canonical allowed stack behavior

Do not copy AP inventory into `shop_profile.json` as if it were locally purchased.

Instead derive an AP entitlement set from the AP ledger/session state and merge it at runtime.

This prevents local profile corruption from becoming AP authority.

## 16.2 AP identity

AP-related Shop progression must be scoped safely.

Local non-AP meta unlocks can be global to the player's launcher profile.

Any AP-specific purchases/check state that can affect a multiworld must be keyed by a stable AP identity, preferably:

- server seed / room identity
- team
- slot

Do not key only by slot display name.

## 16.3 Buying local unlocks while connected to AP

The player may spend local Mental Coins to buy local permanent unlocks.

These are local entitlements.

They must **not** automatically send an Archipelago location check unless the APWorld explicitly created a location for that purchase.

This prevents the client from inventing checks not present in the generated world.

## 16.4 Buying Archipelago items

The requirement also asks to be able to buy "Archipelago items".

Implement this as explicit AP shop checks defined by the APWorld.

Correct model:

- APWorld generation includes a configurable number of `Shop Purchase` locations
- the local Shop UI can purchase/claim one of those locations using a Shop/AP purchase currency or configured Meta Coin cost
- completing that purchase sends the corresponding AP location check
- the item placed there may belong to this player or another player, as normal Archipelago behavior dictates
- the client does not decide which item is granted

Do **not** implement `pay coins -> request arbitrary item from server`.

Archipelago locations are checks; item placement is generated by the multiworld.

## 16.5 Suggested AP locations

Examples:

- `Roguelike Shop Purchase 1`
- `Roguelike Shop Purchase 2`
- ...
- `Roguelike Shop Purchase N`

Optional stage locations:

- `Shop Run Mission 1 Victory`
- ...
- `Shop Run Mission 10 Victory`

Whether mission victories themselves are AP locations should be a YAML option.

## 16.6 AP restart assistance

A failed local run should become easier over time naturally because AP items already received remain available.

This is the desired roguelike/AP behavior.

On a new run:

- rebuild AP entitlement set from received item ledger
- apply current AP unlocks
- allow them in starting loadout according to Shop Mode rules
- preserve AP buff stacks / progression
- never revoke items because the prior local run failed

Optional AP-only assistance can be added later:

`ap_restart_bonus_run_coins`

but should not be required for version 1.

## 16.7 AP goal

If Shop Mode is selected as the generated progression mode, default AP goal:

`Complete one 10-mission Shop Mode run.`

Send goal status after mission 10 victory exactly once.

The APWorld slot data must freeze:

- `progression_mode = Shop Mode`
- run length
- mission pool/filter
- relevant Shop Mode generation settings needed to ensure client/world agreement

The AP server does not need to know the transient local Run Coin balance unless implementing AP data storage intentionally.

## 16.8 AP server data storage

Do not make Archipelago server stored-data the only permanent local meta save.

Local meta progression should function offline.

AP stored data may be used later for cross-device AP-session-specific values, but version 1 should prioritize:

- local atomic profile persistence
- AP item ledger as server-authoritative AP entitlement history

---

# 17. APWorld options

Add Shop Mode-compatible YAML/APWorld options where needed.

Suggested options:

```yaml
progression_mode: shop

shop_run_length: 10

shop_mission_victories_are_locations: true

shop_purchase_locations: 5

shop_starting_extra_unit_limit: 5
```

Do not add options that are purely local UI preferences.

AP generation must validate ranges.

Examples:

- run length: 5–20 if exposed
- purchase locations: 0–25
- extra unit limit: 0–10

If keeping version 1 intentionally fixed at 10 and 5, freeze them in slot data without exposing YAML controls yet.

---

# 18. Mission success reward flow

Add Shop Mode hooks to the existing mission victory handling.

Pseudo-flow:

```python
def on_shop_mission_victory(run, mission_code):
    key = victory_key(run.run_id, run.stage, mission_code)

    if key in run.rewarded_victories:
        return NO_CHANGE

    mission_class = classify_mission(mission_code)

    reward = mission_reward(
        mission_class,
        victory_coin_bonus_level=profile.upgrade_level(
            "victory_run_coin_bonus"
        ),
        modifiers=run.modifiers,
    )

    run.run_coins += reward.run_coins
    profile.meta_coins += reward.meta_coins
    profile.lifetime_meta_coins_earned += reward.meta_coins

    run.rewarded_victories.append(key)
    run.completed_missions.append(...)
    run.stage += 1

    if run.stage > run.run_length:
        run.status = "completed"
        grant_completion_bonus_once(...)
    else:
        run.mission_offers = generate_next_offers(...)

    persist_profile_and_run(...)
```

Use existing application/controller event flow rather than exactly copying this function shape if repository architecture requires otherwise.

---

# 19. Purchase rules and idempotency

Every purchase button must call a pure validator first.

Possible results:

- `ok`
- `insufficient_currency`
- `already_owned`
- `requires_unit_access`
- `max_stacks`
- `not_shop_eligible`
- `run_not_active`
- `purchase_locked_during_mission`
- `ap_not_connected`
- `ap_location_already_checked`

Do not silently fail.

Purchases should persist immediately.

For an ordinary run purchase:

1. validate
2. subtract Ore Coins
3. apply canonical purchased reward
4. atomic-write run
5. refresh UI

For permanent purchase:

1. validate
2. subtract Mental Coins
3. add permanent entitlement/upgrade
4. atomic-write profile
5. refresh UI

For AP purchase check:

1. validate local cost and AP location availability
2. persist local transaction as pending if cost is spent before network acknowledgement
3. send location check
4. reconcile on AP checked-location state
5. never spend twice on reconnect

Prefer only charging once the check is locally committed and keep enough state to resend the AP check after reconnect.

---

# 20. Current mission launch integration

Shop Mode launch eligibility:

- run status is active
- selected mission belongs to current persisted offer
- mission has not already been completed
- no different mission for that stage is already committed/launched
- current state is persisted

Immediately before map generation, build the active Shop Mode reward list.

Suggested helper:

```python
def active_shop_rewards(
    *,
    base_starting_rewards,
    selected_permanent_rewards,
    ap_rewards,
    run_purchases,
    run_buffs,
):
    ...
```

Then reuse current canonical reward/access/buff expansion and map pipeline.

Do not modify native AI campaign technology.

Shop Mode affects player-owned access/clones using the existing randomizer behavior.

---

# 21. Mission launch lock / crash behavior

A player must not be able to exploit launcher restart to choose a different mission after seeing/starting one.

Persist a stage commitment:

```json
{
  "selected_mission_code": "ABC",
  "mission_committed": true
}
```

Commit before launch.

After commit:

- reroll disabled
- other two mission choices disabled
- only the committed mission may be relaunched if the launcher/game crashes before a victory/failure was detected

Do not count a launcher crash as mission failure.

A real detected in-game mission defeat/failure ends the run.

If existing failure detection cannot distinguish crash/quit reliably, use the current repository's failure semantics and document the limitation.

---

# 22. Run setup flow

New run UI sequence:

1. `Start New Run`
2. choose/generate run seed
3. show permanent unlock pool
4. select up to 5 extra units
5. choose optional difficulty modifiers
6. confirm
7. create run state
8. calculate starting Ore Coins
9. create stage 1 mission offers
10. persist
11. enter active Shop Run screen

If connected to AP:

- validate slot data first
- mode/run settings come from AP slot data where authoritative
- AP entitlements are loaded before loadout selection

---

# 23. Configuration and balancing

Create one focused Shop Mode config source.

Recommended:

`configs/shop_mode.json`

Example:

```json
{
  "schema_version": 1,
  "run_length": 10,
  "mission_offer_count": 3,
  "max_selected_permanent_units": 5,

  "starting_run_coins": 5,

  "mission_rewards": {
    "act_1": { "run_coins": 3, "meta_coins": 1 },
    "act_2": { "run_coins": 5, "meta_coins": 1 },
    "operation": { "run_coins": 7, "meta_coins": 2 },
    "finale": { "run_coins": 10, "meta_coins": 3 }
  },

  "run_unit_prices": {
    "tier_1": 3,
    "tier_2": 6,
    "tier_3": 10
  },

  "permanent_unit_prices": {
    "tier_1": 10,
    "tier_2": 25,
    "tier_3": 50
  },

  "permanent_upgrades": {
    "mission_reroll": {
      "max_level": 3,
      "prices": [15, 30, 60]
    },
    "victory_run_coin_bonus": {
      "max_level": 5,
      "prices": [10, 20, 35, 55, 80]
    },
    "starting_capital": {
      "max_level": 5,
      "prices": [10, 20, 35, 55, 80],
      "coins_per_level": 2
    },
    "shop_discount": {
      "max_level": 5,
      "prices": [15, 30, 50, 75, 110],
      "percent_per_level": 3
    }
  }
}
```

Validate config on startup.

Provide sane packaged defaults.

---

# 24. Migration / backwards compatibility

Adding Shop Mode must not invalidate existing state.

Requirements:

- existing users without `shop_profile.json` get a default empty profile
- do not alter old seed state schema unless necessary
- new Shop fields must use normalization with defaults
- corrupt Shop profile should fail safely with a clear backup/recovery behavior consistent with existing storage patterns
- do not reset existing randomizer state to initialize Shop Mode

If schema changes later:

```python
SHOP_PROFILE_SCHEMA_VERSION = 1
SHOP_RUN_SCHEMA_VERSION = 1
```

Add explicit migration functions.

---

# 25. Self-check and tests

Extend `launcher_gui.py --self-check` with pure assertions for Shop Mode.

At minimum verify:

### Economy

- Act 1 reward returns configured values
- Operation reward + level 3 victory bonus adds exactly +3 Ore Coins
- victory bonus caps at level 5
- no failed mission reward helper grants coins
- shop discount never lowers price below 1

### Permanent pricing

- Tier 1 < Tier 2 < Tier 3
- permanent purchase subtracts exactly once
- purchased unlock survives serialize/deserialize

### Unit/buff access

- buff cannot be purchased before unit access
- buff can be purchased after unit access
- buff stack caps remain enforced
- buff itself never grants access

### Loadout

- baseline Tier 1 units do not consume extra slots
- 5 extra selected units accepted
- 6th extra rejected
- canonical duplicates do not create duplicate access

### Missions

- three unique offers where pool allows
- completed mission not reoffered in same run
- reroll changes offer where alternatives exist
- reroll usage persists
- reopening run uses persisted offers and does not regenerate

### Failure

- detected failure marks run failed
- failed run cannot launch another mission
- new run resets Ore Coins and run purchases
- Mental Coins/permanent unlocks survive failure

### Victory idempotency

- processing same victory key twice pays once
- stage advances once
- AP check is not duplicated by local reward processing

### Completion

- 10th victory completes default run
- completion bonus pays once
- no stage 11 offers generated

### Archipelago

- AP item ledger entitlement survives new local run
- AP entitlement is not written as local permanent purchase
- reconnect/replay does not double-grant
- AP shop location cannot be checked twice
- goal is sent after completed run if slot_data goal is Shop Mode

Then run the existing validation:

```powershell
python -m compileall -q .
python launcher_gui.py --self-check
git diff --check
```

Also build APWorld when AP files change.

---

# 26. Implementation phases

Codex should implement in this order.

## Phase 1 — Pure Shop domain

Create:

- config schema/defaults
- model
- economy
- permanent profile normalization
- run state normalization
- mission classification
- mission offer generation
- purchase/access validation

No Tk changes yet.

Add self-check coverage.

## Phase 2 — Persistence

Add:

- permanent profile load/save
- current run load/save
- atomic writes
- migration/version fields
- victory idempotency

Test simulated restart.

## Phase 3 — Standalone Shop Mode UI

Add `Shop Mode` to progression mode choices.

Add own `Shop Run` workspace tab.

Implement:

- new run setup
- three mission cards
- reroll
- Run Coin display
- Meta Coin display
- unit shop
- buff shop
- loadout
- permanent shop/upgrades

Do not add AP purchasing yet.

## Phase 4 — Mission launch and result hooks

Wire active Shop rewards into existing map pipeline.

Wire existing victory/failure detection into run transitions.

Verify a full 10-mission standalone run.

## Phase 5 — Archipelago received-item compatibility

Merge AP-received reward entitlement with active Shop Mode rewards.

Verify:

- death/failure -> new run -> AP items still active/available
- reconnect replay is idempotent

## Phase 6 — Archipelago Shop locations

Extend APWorld:

- Shop progression mode
- optional Shop Purchase locations
- Shop goal condition
- slot data

Wire purchase checks.

## Phase 7 — Balancing / modifiers / polish

Add:

- optional run modifiers
- reward breakdown
- tooltips
- run summary
- completion/failure summary
- better sorting/filtering

Do not balance before core transaction safety is proven.

---

# 27. Acceptance criteria

The feature is complete when all statements below are true.

- `Shop Mode` exists as a selectable progression mode.
- Selecting it shows an entire `Shop Run` tab in the existing application window.
- A new run starts with existing Tier 1 starter access.
- The player can choose no more than 5 additional permanently entitled units.
- Every run requires 10 mission victories by default.
- Every stage offers 3 missions.
- Mission offers show meaningful difficulty/economy class.
- A mission failure ends the run.
- A failed run cannot continue to mission 2/3/etc.
- Permanent Mental Coins survive run failure.
- Permanent unit unlocks survive run failure and application restart.
- Ore Coins reset on new run.
- Mission rewards depend on Act 1 / Act 2 / Operation / Finale class.
- Unit shop purchases cost Ore Coins.
- Buffs can only be bought for owned/unlocked units.
- Existing buff stack limits are respected.
- Permanent unit prices scale by Tier 1 < Tier 2 < Tier 3.
- Permanent reroll upgrade works.
- Permanent victory bonus supports +1 through +5 Ore Coins per successful mission.
- Rerolls are persisted and cannot be regained by restarting the launcher.
- Current mission offer is persisted and cannot be rerolled by restarting.
- Duplicate victory events cannot duplicate currency.
- Existing Classic, Mission List, and Grid behavior remain unchanged.
- Existing deterministic generation for old modes remains unchanged.
- Shop Mode works without Archipelago.
- Shop Mode works while connected to Archipelago.
- AP-received unlocks remain after local run failure.
- Restarting a failed Shop run does not erase AP-received items.
- AP shop purchases are represented as generated AP locations/checks, not arbitrary requested server items.
- AP location checks are idempotent across reconnect.
- Completing a Shop run can satisfy the AP goal when configured.
- All normal self-check/build validation passes.

---

# 28. Explicit non-goals for version 1

Do not add these unless required to make the core feature function:

- multiplayer synchronization of local Ore Coins between multiple humans on one PC
- cloud account/login system
- Steam inventory
- arbitrary AP item purchasing from the server
- procedural combat-stat mutations outside the existing buff system
- multiple lives / resurrection after a mission failure
- daily challenge server
- leaderboards
- online meta-profile synchronization
- replacing the current reward catalogue
- replacing the current map generation pipeline

---

# 29. Important architecture decisions

These decisions are intentional.

## Run vs permanent state

Run state is disposable.

Permanent profile is durable.

AP received-item state is externally authoritative and must be reconstructed from the AP ledger/session.

Do not merge these three concepts into one JSON object.

## AP failure semantics

Local run failure does not mean AP multiworld failure.

The player may start a new local run and continue the same AP slot with all AP items received so far.

## Shop purchases

Run purchases are temporary.

Permanent purchases use Mental Coins.

AP "purchases" are location checks generated by the APWorld.

## Buff eligibility

Buffs never create unit access.

The Shop must use the existing access/buff separation.

## UI

Shop Mode owns a dedicated workspace tab.

It does not replace Grid UI globally and does not require a new window.

---

# 30. Reference behavior from Risk of Rain 2 Archipelago

Use the Risk of Rain 2 Archipelago integration only as a behavioral reference for roguelike restart resilience.

The relevant idea is:

- a run can be lost
- the AP session is still alive
- reconnecting/new runs retain items already earned through Archipelago
- those accumulated AP items make later attempts stronger

Do not copy its C# implementation or item model.

Mental Omega should use this repository's existing AP client, received-item ledger, reward catalogue, launcher, and generated-map architecture.

Reference:

`https://github.com/Ijwu/Archipelago.RiskOfRain2`

---

# 31. Repository-specific integration notes observed before implementation

The repository currently documents these boundaries and they should be respected:

- `launcher_gui.py` is the entry point/self-check rather than the home for feature logic.
- `randomizer/application/app.py` composes Tk controllers.
- `randomizer/application/*_controller.py` and view modules are intended for focused UI orchestration.
- `randomizer/core/storage.py` already provides atomic JSON persistence.
- `randomizer/progression/state.py` already normalizes persisted progression/failure data.
- `randomizer/missions/tier_one.py` already owns starter Tier 1 behavior.
- reward definitions/rules/display/catalogue are split into focused modules.
- the map pipeline already applies access, clones, buffs, and powers.
- the existing Archipelago design keeps mission availability/progression logic in the Randomizer rather than delegating it to AP.
- existing AP received-item handling should be reused rather than replaced.

Therefore, Shop Mode should be implemented as a new progression/economy domain that feeds the existing reward and map systems.

---

# 32. Codex completion behavior

When implementing this specification, Codex should:

1. inspect the exact current repository before modifying files
2. preserve existing interfaces where possible
3. add tests/self-check assertions with each phase
4. keep new modules focused and below repository line-size guidance
5. avoid changing unrelated behavior
6. use data/config for balance values
7. document any assumption that had to be made
8. update developer/user documentation once the mode works
9. report changed files grouped by domain
10. report validation commands and results

If a conflict is found between this spec and an existing safety/determinism/AP invariant, preserve the invariant and implement the closest compatible behavior, documenting the difference.

---

# 33. Suggested first Codex task

Start with **Phase 1 only**:

> Add the pure `randomizer/shop/` domain, Shop Mode config, profile/run schemas, mission classification adapter, three-mission offer generation, economy calculations, permanent upgrade definitions, purchase validation, and self-check coverage. Do not modify the visible UI or Archipelago protocol yet. Preserve all existing RNG behavior by using dedicated Shop Mode RNG derivation.

After Phase 1 passes:

```powershell
python -m compileall -q .
python launcher_gui.py --self-check
git diff --check
```

continue to Phase 2.

This staged approach is required because persistence/idempotency and AP compatibility are more important than quickly producing a large UI patch.
