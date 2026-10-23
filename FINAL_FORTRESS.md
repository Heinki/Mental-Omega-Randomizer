# Final Fortress

Final Fortress (`final_fortress`) is an independent survival module. Select
**Settings → Game Mode → Final Fortress**. Its workspace keeps **Settings**
available; Advanced and Archipelago return when another mode is selected.
Help uses the launcher's themed combobox and contains only **How to play** and
**Wave forecast**. The former Launch status menu/window is removed. The launch
row reports concise readiness or an actual blocking error.

## Co-op over ZeroTier

In **Settings**, the **Final Fortress co-op** section has its own Co-op toggle
and **Co-op players** selector (**2** or **3**), shown only in Final Fortress.
The player count is selected only in Settings and locks while connected.
The campaign **Include challenge maps** option is disabled and
unchecked here; switching modes restores the campaign's saved choices. This
option is separate from Fortress's own enemy Challenge modifiers.

Open **Co-op…** in the Fortress header. The host connects using the human count
from Settings, then shares their ZeroTier Managed IPv4 and pairing code.
Each guest selects **Join**, enters those details and uses a distinct player
name. Guest player numbers are assigned automatically in arrival order. Every PC needs a
separate game installation and matching launcher/game files. The host launches
after the full roster connects. Disconnect the lobby to return to solo play.

There are three friendly seats. With two humans, the host's allied-helper perk
can fill the remaining seat with one AI. With three humans, no AI helper is
spawned, regardless of the purchased helper rank. The three hostile AIs keep
their existing starts and wave rules. Co-op does not automatically multiply
enemy populations; the host still selects difficulty and wave multiplier.

Everyone uses the host's faction and enabled perk ranks for that run, including
starting grants, production/unit/defense bonuses, support powers and periodic
reinforcements. Human armies and reinforcements remain under human control.
Guest-owned perks do not stack onto the host's loadout. Each player's permanent
perks and selections remain their own for future solo or hosted runs.

Survival milestones, camp-pickup Defensive Points and victory/Challenge bonuses
are awarded independently to every player's local Fortress profile. New runs
combine combat kills from every friendly human and AI helper for the kill bonus.
Native score records are matched to the frozen friendly roster by remap scheme
and human name; hostile AI records are excluded. Each house's setup transfers
and its collected cash escrow are deducted before the totals are combined.
Existing run snapshots retain their original local-player scoring.
Camp crates are available from the start, surrounded by their guards. Any human
can collect a camp's single cash/unit crate; its collector receives that in-game
reward, and results name the collector. Collection awards points to everyone.

The host freezes the run before preparation. Guests replay it locally, compare
the exact map digest and acknowledge readiness before the host starts the games.
Each machine watches that run's native markers and saves its own rewards; the
host never replaces a guest's wallet or purchases. Durable joined-run IDs prevent
rejoining an old run from paying twice. Disconnects, mismatched maps and failed
preparations cancel a pending launch without awarding completion points.
There is no mid-game join or reconnect; reconnect all players between runs.

Choose two or three humans once in Settings. Fortress guests connect through
host TCP **19420** and receive player numbers in arrival order: first guest is
player 2, next guest is player 3. The connection dialog has no player-count or
player-number selectors. All players need the updated launcher. Native
game UDP ports are **1234**, **1235**, and **1236** for players 1–3, respectively.
All players must be able to reach one another over ZeroTier. The private-network
firewall helper includes these ports; see [connection setup](COOP_CONNECTION_GUIDE.md).

## Map and objective

The only offered map is **Miners in the Sun**,
`MapsMO/Standard/minersinthesun.map`, **120 × 110**. The human starts at
**waypoint 3, (87, 59)**. Three random, mutually allied enemy countries start at
**waypoints 0, 1, and 5**, at **(94, 152), (83, 175), (143, 175)**. Repeated
countries are supported. The player chooses any native playable country.

Defend Einstein's Lab for **3,600 simulation seconds (one hour)**. The native countdown
is labeled **Until Victory** in game; launcher wall time never awards survival rewards. The
objective is a private installed `CALAB` copy (SteinsTech Lab), with native
1,200 strength and armor. Its **3 × 4 foundation at (91, 57)** is next to the
initial MCV and does not overlap its deployment area. It cannot be sold,
captured, occupied, or chronoshifted. Destroying it causes defeat; surviving
60 minutes causes victory. Three inert, immune AI controllers prevent premature
skirmish elimination victory without producing or participating in combat.

Source terrain, height, resource overlays, and nearby objects were inspected
when moving the Lab and camps. Source skirmish files are never rewritten.
Starting buildings, defenses and power plants check their complete foundations
against the playable `LocalSize` rectangle, including isometric projection and
terrain height, rather than only the packed map diamond. The shipped layouts
have been relocated inside that rectangle. The runtime adapter also rejects
off-map added objects before writing launch files.

Enemies start with **indestructible construction yards**, using Ares' per-country
construction-yard start; the player and helpers keep their normal MCV start.
Enemy construction, power-plant variants, upgrades and deployed building forms
use private immune copies. Enemy MCVs deploy into those same copies, and AI
production lists, prerequisites, refineries and docks recognize them. These
protections do not apply to the player's buildings or ordinary enemy troops.
Each enemy additionally starts with **24 indestructible defenses**: eight basic,
eight anti-air and eight advanced faction turrets, around its playable base
perimeter. They require no power and cannot be captured or sold. Base centers
remain open for native AI construction. Destroying enemy bases is not an
alternate survival victory condition.

## Waves

Extra waves begin at minute **5**, repeating every five minutes through minute
55. One enemy side joins at minute 5, two at minute 10, all three from minute
15. A separate seeded shuffle chooses joining order. Normal AI economies,
production, and attacks continue throughout.

Casual / Normal / Mental starts with **3 / 6 / 9 units per active side**.
Each later wave adds that opening base amount, then applies the independent
**x1–x10 multiplier**. All twelve country pools mix infantry, vehicles,
anti-air, and artillery/support units, with four alternative compositions at
minutes 5, 15, and 25, including infantry-led and mobile columns.
From minute **15**, faction air support replaces **15%** of each wave; from
minute **30**, the share becomes **25%** and heavy aircraft enter the pool.
At least one flying unit is included when the ground roster leaves space.
These counts are taken from the existing wave budget, rather than added above
the cap. Infantry and every selected ground identity remain represented.
Air teams attack separately from ground teams and use the same reusable slots.
The native armed flying vehicles include Warhawks/Thors, Wolfhounds/Kirovs,
Invaders/Basilisks and Buzzards or Condors/Pteranodons. These use native flight
and weapon rules without requiring an aircraft docking/rearming arrangement.
`wave_air_support` configures start times, percentages and country pools.
Native attack scripts seek hostile targets immediately;
they do not first move onto an MCV waypoint that a construction yard may occupy.

Provisional ceilings remain **480 per wave and 480 reserved wave units**.
New plan-16 runs divide that living budget into eight reusable 20-unit slots
per enemy (160 each, 480 shared). Waves are delivered as mixed groups of up to
twenty, alternating active fronts. An empty slot is reused immediately; a few
survivors no longer reserve an entire earlier wave. Each group still holds its
slot until every private identity is absent, including converted or captured
units. Normal AI armies and fixed camp guards are excluded. Delivery waits when
that enemy's slots are occupied; the next five-minute interval starts after the
entire wave has been delivered. Victory/defeat stops pending deliveries.
Older frozen plans retain their whole-wave reservation policy.

Each enemy receives a walkable, unbuildable 5x3 arrival apron beside its base:
waypoints 16/17/18 at (95,148), (81,169), and (144,167). These replace occupied
construction-yard spawn points. `map.enemy_wave_positions` stores each apron's
top-left corner. The native terrain audit checks all fifteen cells.
Enemy wave deliveries now use native action **80 (reinforcement at waypoint)**,
with the same explicit waypoint in the action and its TeamType. Previously they
used generic action 7, which supplies no placement override to the native engine;
the audit checked the TeamType waypoint but did not check explicit action placement.
The launcher now rejects an enemy arrival apron more than 16 cells from its own
base or less than 32 cells from the human or an active helper start, checking the
entire apron using cell-grid distance. This adapter correction also applies when
rebuilding an older frozen plan; pre-16 waves retain their original enemy starts
and receive explicit placement there. Existing native saves need a fresh launch
to receive regenerated triggers. Live confirmation of the reported misplaced
waves remains pending; generated-map audits do not simulate native placement.
Immortal enemy buildings, MCVs and fixed defenses have `LegalTarget=no`; helper
assault scripts that insisted on buildings/factories/defenses now seek any
hostile legal target. Their normal production and starting/arrival armies share
this restriction.

**Mental AI Boost** is an optional checkbox in Defense setup, saved separately
per profile and frozen into each new run. It applies the installed client's
`INI/Game Options/Mental AI.ini` to both hostile and allied AI, including private
factory copies. This includes parallel AI queues, increased factory counts,
economy bonuses and faster team creation. Native AI production is outside the
scripted-wave ceiling. The option defaults off when migrating existing profiles.

A separate **Next enemy wave** countdown appears beside **Until Victory** in
new plan-17 games. It uses a private hidden, non-firing recharge display with the
configured five-minute interval; it does not replace the survival mission timer.
The clock resets after the full enemy wave is delivered. At zero it can remain
pending while capacity is occupied. It disappears after the last scheduled wave
or when the run ends. Its zero-power, immune hidden provider adds no buildable
power, damage, cash or usable sidebar ability. Its one setup ownership transfer
is excluded from performance Defensive Points, and removal has no explosion or loss voice.

The adapter supports eleven waves,
six distinct types per reinforcement group, six camps, 100 local flags, and
the native 511-byte action-line limit.

## Defensive Points, perks, and results

Final Fortress uses **Defensive Points** for permanent perk purchases, separate
from Shop Mode Gems. Existing balances and saved runs keep their values. Internal
save/configuration keys such as `gems`, `gem_cost`, and `gem_rewards` retain their
legacy names for compatibility.

Survival grants **25 Defensive Points at minute 25**, another **25 at minute 45**, and
**50 on victory at one hour**: **25 / 50 / 100 total survival Defensive Points**. Earlier milestones
remain earned after defeat or quit. Verified native victory or defeat also
allows **5 Defensive Points per 50 native kill-score points**, capped at **100 Defensive Points**.
Setup ownership transfers and claimed cash escrows are excluded from that
score. Native score accounting can include captures; it is not a separate
combat log. Unfinished quits grant no kill bonus.

Permanent purchases and upgrades enable the perk automatically for the next
run. The table shows purchased rank, enabled/disabled status, and the next
upgrade price. Select a row to see **Rank 1 / Rank 2 / …** cumulative effects
beside the list, including exact units, buildings and powers for the selected
faction. The resizable side panel uses the launcher theme and does not take
height away from the perk list. The list has one vertical scrollbar and no
horizontal scrollbar. Rank text scrolls with the mouse wheel or keyboard,
without a second scrollbar. Prices appear only in **Next rank cost**. Use
**Disable perk** to omit an owned perk without losing its purchased ranks.
Purchases remain available after restarting. An active run keeps its frozen
loadout; perks can be changed once that run finishes.

For local source-checkout gameplay testing, choose **Profile → Testing (all
unlocks)** in the Fortress header. This selector is available only when the
checkout already has its ignored `final_fortress_testing_state.json` save.
Compiled EXEs always use Standard progression, hide the profile selector and
reject all-unlocks initialization, even if a testing save is copied beside
their ordinary data. Personal progression files are not included by the EXE
build's explicit asset/config packaging rules.
All twenty-two perks are purchased and enabled at maximum rank,
including both faction superweapons and two helpers. The initial faction is
Russia, difficulty Normal, wave multiplier x1; Challenge modifiers start off.
Switch faction or disable individual perks to isolate effects. This profile
uses `final_fortress_testing_state.json`, with its own Defensive Points and run results.
**Standard** retains normal progression in `final_fortress_state.json`.
The launcher starts on Standard; profile switching is locked while preparing,
running or collecting the final game results. Existing testing selections are
preserved when switching away and back. Newly added perks are unlocked and
enabled automatically, and purchased testing ranks stay at their configured
maximum. Existing Defensive Points and frozen runs/results are preserved. A clean source
checkout does not expose or automatically create a testing profile.

## Ranked permanent perks

All prices below are provisional and configurable in `configs/final_fortress.json`.
Each rank stores its complete cumulative effect, rather than adding the previous
rank's effect a second time. Prices are paid once per rank.

| Perk | Rank prices (Defensive Points) | Maximum effect |
| --- | --- | --- |
| Supply cache | 30 / 60 / 120 / 220 / 360 / 540 | Six ranks, +2,000 credits each, up to +12,000 |
| Production speed | 40 / 80 / 140 / 220 / 340 | 25% shorter infantry, vehicle/naval, aircraft, building and defense production time |
| Starting army | 40 / 80 / 140 / 220 / 340 | 3 / 6 / 9 / 12 / 15 faction units; advanced infantry, artillery, T3 vehicles, one faction hero at rank 5 |
| Veteran army | 60 / 120 | Veteran, then Elite (highest veterancy); two infantry at that rank instead if Starting army is disabled |
| Starting buildings | 50 / 90 / 150 / 230 / 350 | Power plant, barracks, refinery with harvester, radar, war factory |
| Starting defenses | 40 / 80 / 150 / 260 | Four of every unlocked defense type through T3, plus starting power plants |
| Veteran defenses | 120 | Starting and subsequently built defenses begin veteran |
| Defense firepower | 100 / 200 / 360 / 560 / 820 / 1,160 | Six ranks, +10% damage, fire rate and range each, up to +60% |
| Tier 1 units | 200 / 300 / 450 / 650 / 900 / 1,250 | Six ranks, +5% health, damage and fire rate each, up to +30% |
| Tier 2 units | 400 / 600 / 900 / 1,300 / 1,800 / 2,500 | Same 30% cap, independently purchased |
| Tier 3 units | 600 / 900 / 1,350 / 1,950 / 2,700 / 3,750 | Same 30% cap, independently purchased |
| Faction support powers | 180 / 360 / 540 / 720 / 900 | Five independent cloned powers; one additional faction power per rank |
| Faction superweapons | 500 / 1,000 | Secondary power first; second rank retains it and adds the offensive superweapon |
| Power upgrades | 160 / 280 / 440 / 650 / 920 / 1,260 | Six ranks improving compatible effects of unlocked perk support powers and superweapons |
| Satellite intelligence | 150 | Reveal the entire map immediately |
| Allied helpers | 300 / 600 | Up to two normal skirmish AIs sharing the player's faction and enabled perks |
| Special unit access | 300 / 600 / 1,000 | One additional faction special production unlock per rank, retaining earlier unlocks |
| Periodic reinforcements | 80 / 160 / 280 / 440 / 650 / 900 / 1,200 / 1,600 | Every five minutes: 10 / 14 / 18 / 21 / 24 / 25 units; rank 7 makes the full roster Veteran, rank 8 Elite. Shared 150-unit living cap |
| Automatic healing | 100 / 220 / 400 | Eligible rookie units and defenses heal 1% / 2% / 3% of maximum HP per native healing tick; stronger existing healing remains |
| Sight and stealth detection | 80 / 160 / 280 | +1 / +2 / +3 sight, plus supported cloak sensors; existing longer sensor ranges remain |
| Unique-unit capacity | 150 / 300 / 550 | +1 / +2 / +3 to eligible positive live-unit production limits, including unlocked specials; no new access |
| Special building income | 120 / 240 / 420 / 650 | +5 / +10 / +15 / +20 credits per existing payout cycle on eligible special buildings |

Utility perks reuse reward-catalogue eligibility, exclusions and calculations,
including linked deploy/mutation forms. They affect private player/helper
copies. Healing starts at rookie rank and uses the unit's actual buffed HP and
native healing interval. Sight and sensors apply only to supported types.
Capacity increases positive unit limits, preserving normal ownership and
technology requirements; it does not make gift-only units buildable. Income
applies to normally constructed private Ore Purifiers, Industrial Plants,
Cloning Vats and Reprocessors, preserving their prerequisites and payout delay.
It does not grant buildings, change ordinary structures or create an additional
income source. Captured native copies retain their native payout.
The Ore Purifier's base periodic payout is 20 credits: income ranks 1–4 pay
25 / 30 / 35 / 40 credits per native 100-tick cycle. This is a flat recurring
cash bonus, not an increase to the ore-sale percentage. Rank descriptions show
the actual total payout for each eligible building.

New runs reserve the reviewed 5x3 reinforcement apron beside each friendly
base using passive, invisible, indestructible 1x1 foundations. Infantry and
vehicles can walk over them, but buildings cannot occupy the arrival cells.
Reservations exist only when periodic reinforcements are enabled. Helpers'
starting armies and periodic arrivals receive explicit attack-team orders;
their unique tracked arrival types cannot rely on ordinary AI recruitment.
Human arrivals remain under the player's control.

Native and private production types use ordinary alternative prerequisite
lists for shortcut buildings. This retains those shortcuts while enforcing
house and technology gates, preventing the original Harrier from appearing
beside its buffed private copy through `PrerequisiteOverride`.

Special access grants production through the faction's ordinary war factory,
not free starting units. The three cumulative unlocks are:

- Allies: Paladin Tank Hunter, Quickshifter, Paradox Engine.
- Soviets: Apocalypse Tank, Syckle, Perun Flagship.
- Epsilon: Wormqueen, Ganzir Defender, Hand of Ereshkigal.
- Foehn: Phantasm MLRS, Seitaad Ballista, Archelon.

These are private reviewed reward models, including the portable Paradox Engine
and Hand of Ereshkigal fixes and Archelon's deploy conversion. Mission and
stolen-tech gates are replaced only on those private copies. Native unit credit
costs and unique build limits remain; existing Tier perks also buff eligible
special copies. All three countries within each faction family currently share
this configurable sequence. Helper AI receives the same access, but its native
production recipes still decide which units it builds.

Periodic reinforcements first arrive at minute 5, then every five minutes through
minute 55, strictly before victory. Rank 1 gives ten basic faction infantry.
Higher ranks retain them and add four basic vehicles, four advanced infantry,
three artillery, three T3 vehicles, then one special unit, respectively. Exact
country rosters appear in the rank descriptions. Rank 7 retains the complete
25-unit roster and grants Veteran arrivals; rank 8 makes them Elite, the highest
native veterancy. Counts, five-minute timing and the living cap do not increase
for those last two ranks. Units spawn at reviewed army staging points near each
friendly base. Human arrivals guard for player commands; helper arrivals and
starting armies receive explicit attack teams. Those teams consider every
hostile house, matching native AI targeting, rather than restricting themselves
to one primary enemy. Unit Tier perks apply; Veteran army remains a separate
starting-army bonus. Reinforcement rank is native TeamType.VeteranLevel 1/2/3
for Rookie/Veteran/Elite and does not promote ordinary factory production.

Reinforcements have a separate **150 living-unit cap shared across the player
and helpers**, excluding starting grants, production and enemy waves. New plan-17
runs share fifteen reusable ten-unit groups across the entire coalition; there
is no fixed per-house quota. Each group remains reserved until its private types,
including captured/converted units, disappear. A few survivors therefore hold
at most ten slots rather than an entire 75-unit coalition arrival. Partial final
groups still reserve ten, so this remains a conservative ceiling.

Each house delivers its own complete roster in mixed groups and starts its next
five-minute timer independently. A helper's incomplete arrival no longer holds
the human's timer. All houses still wait when shared capacity is occupied; a
one-time on-screen message explains that wait during a pending human arrival.
The next free group resumes automatically. Arrivals spawn at the center of their
existing protected 5x3 aprons, whose invisible passable foundations prevent
building over the spawn cells. No further arrivals occur after the objective
ends. Older frozen plans retain their whole-arrival policy. Counts, rosters,
prices, timing and cap remain provisional configuration values.

Helpers use unused waypoints **6 (141, 68)** and **7 (147, 47)**, allied with
one another and the player, and hostile to all three enemies. Each receives
the same starting grants, production bonus, private unit/defense buffs and
support powers. They retain native skirmish construction and team recipes.
The three-enemy wave schedule and shared scripted-wave limits are unchanged.

Perk armies use faction-native rosters. Source technology levels use the same
T1/T2/T3 classification as Grid. Health/damage round down and reload time rounds
up so integer rounding cannot exceed the configured percentage cap. Mind-control
weapon damage remains a capture count; fire-rate and defense-range bonuses can
still apply. Spawn-manager pseudo damage is not multiplied. Sister-subfaction
gifts use unbuildable private copies when necessary, preserving normal faction
production restrictions.

Player and helper copies have concrete country production gates. Enemy copies
and original human definitions retain their separate stats. Native base-unit,
harvester, refinery/docking, prerequisite, and AI defense lists recognize the
private types. Preplaced refineries omit their automatic free unit and receive
one explicit faction harvester, avoiding duplicate or missing harvesters.
`map.perk_layouts` contains source-audited building, defense and army positions
for all three friendly starts, with the MCV deployment area reserved.
Native infantry, vehicles and aircraft also receive explicit concrete
`RequiredHouses` gates derived from their actual ownership restrictions. Private
prerequisite equivalents can no longer expose foreign units such as Virus in
the Euro Alliance roster. Starting-army ranks now use the correct preplaced
object experience values: **100 for Veteran, 200 for Elite**. TeamType ranks use
a different representation and are unchanged. Older frozen runs keep their
original snapshots; start a new run to apply the corrected layouts and ranks.

The defense perk starts with four basic turrets in outer approach batteries.
Each upgrade adds four of the next defense type while retaining the earlier
groups, for **4 / 8 / 12 / 16 defenses**. New plan-15 positions are at least
twenty map cells from their starting MCV, leaving the central expansion area
free. Human batteries follow the marked front/right approach arc outside the
starting structures; helper batteries also cover outer approaches. Terrain,
whole foundations and playable edges are checked for every country. All three
friendly starts have sixteen defense slots and twelve power-plant slots.
Power grants use the selected faction's normal plant and cover all granted
defenses plus the demand of the five optional starting buildings, without
relying on that other perk's power plant. For the current Soviet values,
ranks supply **3 / 4 / 6 / 10 Tesla Reactors**. Quantities and positions remain
configurable. Existing committed runs retain their frozen layouts; create a new
run to use the revised outer batteries.

The first two support ranks remain **Airborne / Repair Drone** for Allies,
**Spy Plane / Instant Shelter** for Soviets, **Scout Raven / Vision** for
Epsilon, and **Knightfall / Spinblade** for Foehn. Each later rank adds one
power from the selected country's installed roster:

| Country | Rank 3 | Rank 4 | Rank 5 |
| --- | --- | --- | --- |
| United States | Kingsnakes | Black Widow | Chronoboost |
| Euro Alliance | Paladin Aid | Lightning Rod | Chronoboost |
| Pacific Front | Cryoshot | Glacial Screen | Black Widow |
| Russia | Tank Drop | Overcharge | Rad Attack |
| Latin Confederation | Motor Ambush | Irradiation Beta | Rad Attack |
| China | Irradiation Gamma | Repair Drones | Pack Attack |
| PsiCorps | Magnetic Beam | Libra Clones | Regen Drugs |
| Scorpion Cell | Toxic Strike | Bloatick Trap | Regen Drugs |
| Epsilon Headquarters | Shadow Ring | Ruiner | Regen Drugs |
| Haihead | Chaos Touch | Decoy Team | M.A.D. Mine |
| Coronia | Decoy Squadron | Harbinger | Decoy Team |
| Last Bastion | Sweeper Drop | Chaos Touch | Decoy Team |

These use private power IDs and native repeating-power grants, independent
of normal faction unlocks. Native names, artwork, recharge times and use costs
remain intact. Auxiliary-building and designator gates are removed from the
private powers. All five ranks and prices are configurable per country.

Faction superweapon ranks are cumulative:

| Faction | Rank 1 | Rank 2 adds |
| --- | --- | --- |
| Allies | Chronosphere | Lightning Storm |
| Soviets | Iron Curtain | Tactical Nuke |
| Epsilon | Rage Inductor | Psychic Dominator |
| Foehn | Nanofiber Sync | Great Tempest |

Both powers use the existing reviewed portable templates and their compatible
power upgrades. Chronosphere receives a private linked destination power;
Foehn Nanofiber uses the proven portable missile chain rather than a hidden
cannon. Nanofiber transformations preserve friendly tier buffs through private
mutation forms, armor and animation registrations. Enemy native forms retain
their existing definitions.

**Power upgrades** uses the same reviewed capability definitions and private
clone planner as Grid/Shop. Each rank adds one stack of every compatible
upgrade to the enabled perk powers: recharge, activation cost, effect area,
damage, payload health, effect duration, status-effect strength, vehicle
targeting, scouting vision and delivered unit/aircraft count. Each power gains
only the capabilities listed for it, respecting each capability's existing
cap. For example, scouting vision and payload can reach six; recharge and
duration retain their five-stack caps. The perk never grants a missing power
or changes native enemy powers. Helpers receive the same selected upgrades.

New runs give each unlocked power its own hidden owned launch provider, so
house filtering works for GenericWarhead effects beyond the first two powers.
Great Tempest's private repeated-damage animations and Nanofiber's private
mutation forms receive the same generated art and early registry preload as
Grid/Shop. Power prices and upgrade values
are provisional; unlocks and rank counts are configurable in the Fortress
catalogue, while reviewed per-power capabilities use `rewards/power_buffs.json`.

Legacy purchase IDs and balances are retained. The former six-unit
Reinforcements purchase migrates to Starting army rank 2. Previous run snapshots
and reward receipts retain their original prices and effects.

**Run results opens automatically on the Final Fortress tab after victory or
defeat.** It also reports earned receipts when a run is abandoned. The header
shows the outcome, map, and total Defensive Points from that run. Rows separately show
survival milestones, completion, each enabled Challenge bonus, camp claims,
actual crate outcomes, and kill bonuses. Totals come from the committed run's
claimed events and frozen prices, not the current balance or current JSON.
The latest result remains available after restarting the launcher.

## Challenge stacks

Challenge offers **46 modifiers**: the 41 Grid enemy stat/production definitions,
Powerhouses, three reinforcement powers, and a faction offensive-superweapon
toggle. Grid effects come through
`randomizer.rewards.enemy_scaling`. Drag across rows or Shift-click to select a
range; Ctrl/Alt-click adds or removes individual rows. **Select all** or
**Ctrl+A** selects the entire list. **Enable selected**, **Disable selected**
and **Max stacks** apply to the selected group in one atomic profile save.
Double-click or Space enables a mixed group, or disables a fully enabled group.
Left/right arrows appear
**inside each modifier row**, directly beside its stack count, and change it
immediately. Repeated arrow clicks adjust the count without toggling the
modifier. The complete selected effect appears in a themed, word-wrapped panel
beside the list, with a resizable divider. Long descriptions scroll with the
mouse wheel or keyboard. This preserves the list's height and avoids clipped
single-line effects or horizontal scrollbars. **Max stacks** sets each selected
modifier to its own actual cap. Editing stacks preserves enabled/disabled status;
there is no Apply button or small enable checkbox. **T1 Unit Armor ×3**, for example, uses the same
Grid formula and eligibility rules. Country armor/production and T1/T2/T3
health, armor, mobility, vision, firepower, fire rate, range, ammo, healing,
cloaking, and sensors are available. Grid's individual stack limits apply:
usually five; cloak, sensors and the five new Challenge toggles use one.

- **Powerhouses** gives each active wave side two rotating faction heavies and
  upgrades that wave team to veteran. It uses Grid's heavy pools. When room
  remains, two units are added; at the existing 480-unit ceiling, heavies
  replace ordinary units. Their private identities share the existing living
  wave cap and deploy-conversion tracking. This mode has no Shop stage bonuses
  or additional uncapped companion teams. Victory bonus: 25 Defensive Points.
- **Paratroopers**, **Bloodhounds** and **Moon reinforcements** are independent
  toggles, worth 20/25/30 victory Defensive Points. Each hostile AI receives an AI-only
  repeating power, with three launches per power, twice the reviewed native or
  portable recharge interval, and no initial ready shot. Paratroopers use the
  enemy faction's basic infantry; Bloodhounds and Moon reinforcements retain
  their reviewed payloads. The native auto-targeting behavior is reused.
- **Faction offensive superweapons** grants every hostile AI its own family
  weapon: Lightning Storm, Tactical Nuke, Psychic Dominator or Great Tempest.
  One toggle covers all factions, including repeated enemy countries. These
  are private AI-only copies with native recharge, no initial ready shot and
  no player power upgrades. Victory bonus: 60 Defensive Points.

Enemy powers have owned invisible launch providers and are preloaded before
house creation. Native powers, human powers and helper powers keep their own
definitions and permissions. Native power-delivered armies are outside the
scripted-wave living cap, but the three-shot budget bounds their lifetime
reinforcement output: at shipped settings, all three reinforcement toggles
across all three enemies create at most 261 units over the whole run. Ordinary
AI production is also outside the scripted-wave cap. Launch counts, recharge
multipliers and victory Defensive Points are provisional configuration values.

The default victory bonus is **5 Defensive Points per enabled stack**, configurable per
entry. Country multipliers affect only private enemy country derivatives.
Tier calculations reuse `enemy_native_unit_buff_rules`; results are placed on
private enemy TechnoTypes and weapons. Native human definitions remain intact.
Concrete country production gates hide AI copies from human factories, including
when both sides selected the same parent country. Country-scoped copies of native AI triggers, teams and task forces request
the appropriate enemy or helper counterparts. Scripted waves
and camp guards receive the same applicable stat changes.

The Soviet Field Bureau's building-provided Drakuv power now uses a private,
early-preloaded power and the reviewed RAVA player template. Its provider and
designator reference the private Field Bureau, and its payload retains
`Image=RAVA`, normal build timing and valid training behavior. The native
Field Bureau, recharge, credit cost and power requirements are preserved.
This does not grant an extra perk power or unlock Drakuv factory production.
Native delivery at the reported freeze still needs a fresh-match gameplay check.

## Camps and random crates

Six camps span the playable map: north-west **(32, 129)**, western approach **(72, 96)**,
central **(153, 128)**, east **(179, 79)**, northern pass **(134, 105)** and
south-east **(202, 113)**. Guard positions and crate claim cells use clear, level playable
terrain and avoid base deployment areas and fixed building foundations. The
former west and south-west camps were inside protected enemy base approaches;
new runs move both onto the accessible battlefield. Every crate and guard
position is at least 40 cells from each hostile start. Guard formations can
stand on walkable ore/gem overlays; crate cells always remain overlay-free.
Guards use native Area Guard with a six-cell acquisition radius, keeping their
fight local rather than sending survivors on a global hunt. Each camp's crate
is available from the start; destroying its guards is optional for collection.
New runs use **5 / 8 / 12 guards on Casual / Normal / Mental**, multiplied by
the wave multiplier and capped at **30 per camp / 180 across all six camps**.
Camp rosters are selected independently of the three enemy base factions.
Allies, Soviets, Epsilon and Foehn each appear before any faction repeats, so
all four are represented across the six camps every run. A seeded subfaction
choice supplies each camp's infantry, vehicles and artillery; difficulty
influences the early/mid/late composition selection. Camp ownership still uses
the configured enemy AI, including its alliances and applicable Challenges.
The former nearby starter camp now occupies the western approach at **(72, 96)**.
Every guard position is at least 32 cells from all active friendly starts. It
uses the same mixed faction formations, **5 / 8 / 12** base counts and
**30-guard** ceiling as the other camps. Every camp has a configurable **35%
chance** of including one faction hero or heavy unit. Last Bastion uses Uragan
for its starting-army hero, special-unit crate and camp hero pool.
Counts, limits, special pools and chance are configured through `camp_balance`
and frozen before launch. Each camp has thirty reviewed clear, level guard
positions rather than extending a formation into nearby terrain.
Collecting a camp crate grants **10 Defensive Points immediately**, together
with its frozen cash or unit reward. New plans (version 25) create all six crates
at startup, independently of guard deaths. Startup emits no clearance messages,
reward receipts or points. Each ready trigger disables itself, creates one
crate and enables the human-only pickup. Co-op collectors share a claimed flag
so the first human receives the in-game reward exactly once.

Guard ownership uses the existing timed Action 14 transfer, stopped after one
second. Guards retain their local Area Guard orders, Challenge bonuses and kill
scoring. No garrison or retaliation TeamType recruits these private copies.
Guard deaths no longer determine crate availability or Defensive Points: live
feedback showed both premature clearance and missing crates with death tags.

Messages use short literal text chunks, each at most **31 bytes including
`NOSTR:`**, to fit the native 32-byte trigger field. Camp names, awarded points,
crate instructions, collected rewards and co-op collector names are split
before serialization instead of being silently truncated.

Player entry at a camp's crate cell claims its Defensive Points and one frozen
random in-game reward:

- **40%:** 2,500 credits.
- **30%:** 10 Tier 1 units.
- **20%:** 5 Tier 2 units.
- **10%:** one faction special unit.

Squads and special units use the chosen player's installed faction rosters.
Weights, credit amounts, unit compositions, and counts are configurable.
Outcomes are seeded independently per camp and saved before launch, so reloads
or configuration edits cannot reroll a committed reward.
The results panel shows uncollected crates and each collected reward.
Plans before version 18 retain their original five guards and pickup-based Defensive Points
rules. Plans 18–24 retain their original death-based Defensive Points rules,
camp positions and frozen formations,
including the smaller infantry-only starter camp in plans 21–22. The relocated
mixed camp applies to new runs.

Native visual crates remain physically collectible by AI; their ordinary cash
is disabled. Only player claims trigger the real cash/unit reward, and AI pickup
does not consume that claim. Cash uses a passable, invisible,
immune building escrow at an unused start: its one-time transfer pays only the
player. Unit rewards arrive at the camp through separate player-owned teams for
each frozen unit type. Each uses native Action 80 with the explicit camp waypoint,
replacing the implicit Action 7 mixed-squad delivery that produced partial live
rewards. The emitted teams preserve the complete configured composition (ten
Tier 1 units or five Tier 2 units). Escrows are not combat units and have no
production or recurring income.

## Persistence, runtime files, and isolation

Feature code lives in `randomizer/final_fortress/`. `challenges.py` adapts the
shared Grid definitions/calculations; `reporting.py` formats run receipts;
`application/final_fortress_controller.py` owns mode selection, UI, launch,
polling, and cleanup. `perks.py` validates and resolves purchased ranks;
`player_perks.py` adapts private friendly types, native AI and support powers.
Shop and Grid gameplay modules are not modified.
Shared Settings and game speed remain accessible, while Final Fortress
country, difficulty, multiplier, Challenges, Defensive Points, and perks use separate state.

The adapter reuses ordered INI helpers, installed rules, the runtime asset
lease, Syringe/Wine launch, empty native marker teams, and shutdown monitoring.
It writes leased `spawnmap.ini` and `spawn.ini`. Private countries and perk definitions also create a
complete temporary `rulesmo.ini` from the installed cache, registering private
countries before multiplayer house allocation. A complete temporary `aimo.ini` retains native recipes with country-scoped
private task-force requests for enemy and helper production. Existing custom loose files are never overwritten.
Cleanup removes only launcher-marked temporary rules/AI files and respects
another live launcher's runtime lease.

Enemy teams use the unique concrete countries `FFENEMY1`–`FFENEMY3`; reward
teams use the player's concrete country. Transfers use configured **starting
positions**, not MultiN ordinals. New techno/power types use reserved registration keys from 20000; country
indices remain contiguous for the native spawner. Fresh
execution markers contain a digest of the exact committed run ID. The watcher
starts at the old log boundary, handles replacement/truncation and partial
lines, requires the matching START, and reads real team-creation messages.
Generic Winner rows alone never award a result. Event receipts are atomic and
deduplicated. Only verified score tiers may be credited after a terminal result.
The checkpoint contains only the 64 bytes immediately before the read cursor;
an unread log backlog cannot be mistaken for file replacement. Shutdown waits
until the final log tail is consumed before classifying an unfinished run.
Active or abandoned saved runs can recover from matching native START and
terminal markers in the retained debug log. Recovery runs in the background,
backs up the original save, preserves the frozen reward values and credits only
missing receipts. Replaying the same evidence cannot award Defensive Points twice.

Normal progression uses `final_fortress_state.json` and its OS lock; the
optional testing profile uses its separate state file and lock.
State schemas 1–8 migrate to schema 9 without resetting Defensive Points or ownership.
Schema 9 adds durable co-op run IDs and a local player index on co-op runs;
guest run snapshots can contain host-owned perks without granting their ownership
to the guest's permanent profile. Plan 22 freezes the human roster, fills only
unused friendly seats with helpers, and records each human's setup-score correction.
Plan 23 freezes the full friendly score roster and each house's transfer
correction. Its revised layouts reserve a conservative 7x7 deployment/exit
area around every active MCV. Starting buildings, power plants, friendly army
staging and the affected enemy arrival apron were moved outside that area;
launch validation rejects new overlaps.
Plan 24 relocates the two base-overlapping camps and validates the complete
40-cell hostile-base exclusion at launch. Plan 25 replaces death-based camp
clearance with startup crates and pickup-based points. It also uses separate
per-type reward teams with explicit camp arrival waypoints. Plans through 24
keep their frozen death-based receipts.
The former sole offensive-superweapon purchase becomes rank 2, preserving
that weapon while also granting the new secondary power. New rank-1 purchases
unlock only the secondary power.
Version 16 adds reusable enemy wave slots, protected arrival aprons and the
frozen Mental AI Boost selection. Version 17 adds independent friendly delivery
chains with shared small groups, centered arrivals and a synchronized wave clock.
Version 18 freezes scalable faction camp rosters, reviewed guard positions and
separate camp-clear Defensive Points and crate-claim receipts. Version 19 selects camp
rosters independently of enemy countries and guarantees all four faction
families across the six camps. Version 20 freezes staged wave air support,
preserving total wave populations and ground identities with separate flying
attack deliveries. Version 21 freezes a separate basic-infantry roster and lower
difficulty-based population ceilings for nearby starter camps. Earlier plans
retain their original inputs.
Plans 1–6 retain their original snapshots; version 6 adds stack selections and
per-camp random reward snapshots, and version 7 freezes purchased perk ranks,
cumulative effects and allied helper starts. Version 8 adds frozen starting
power grants and expanded defense layouts, including their transfer-score
correction. Version 9 adds power-upgrade stacks and combines faction
superweapon unlocks with the private perk powers; its transfer-score offset
counts one launch provider per unlocked power. Version 10 adds private
Nanofiber mutation chains for tier-buffed Foehn units. Older plans retain their
original provider layout and effects. The old three-option Challenge contract
remains readable for existing run snapshots. Damaged state reports an error
rather than silently resetting progress.

## Validation and limits

Follow `AGENTS.md`: compilation, existing installation/domain checks, source
map audits, and actual launcher/native gameplay checks. No unit tests.

`python3 tools/audit_final_fortress_maps.py --output /tmp/fortress-map-audit`

Use `--humans 2` or `--humans 3` to audit co-op maps and emit every human's
native spawn file. `tools/fortress_coop_audit.py` also reviews house/peer ordering,
AI seat limits, shared camp pickup guards, human control, native satellite reveal
and actual per-house setup transfers. Add `--terrain` for placement/ground checks.
Live two/three-PC ZeroTier gameplay, synchronized objectives and disconnect
behavior still require manual multiplayer verification; these audits never open
game windows or change player saves.
generates reviewable variants of **Miners in the Sun only**, plus spawn files,
without opening the game or changing player progression. The default 108
configurations cover all twelve countries and
three difficulties with baseline, helper-only and maximum perk/Challenge
loadouts. It checks native references, country registration, runtime preload
coverage, action/flag limits, source terrain preservation, building foundations,
MCV deployment space, starting unit placement, explicit hostile arrival actions,
enemy/friendly spawn separation and spawner metadata. It does not
simulate unit behavior or establish frame-rate limits. No other playable maps
are introduced or audited by this command.

The explicit enemy-arrival correction passed all 108 baseline/helper/maximum
configurations with terrain checks across all countries and difficulties. Saved
plans 7 and 18 also regenerated successfully with explicit hostile spawn actions.
Python compilation passed. These checks leave the source map and player saves
unchanged; the reported live placement still needs a fresh-match gameplay check.

For placement changes, use `--profiles maximum defenses --difficulties normal
--terrain` to check the twelve factions with and without other starting perks.
This optional check decodes the source's packed terrain using the system LZO2
library, avoiding resources, trees, invalid foundations and uneven ground.
The current perimeter layouts pass all 24 configurations, including the
starting power budget and transfer-score correction.

Result handling batches verified receipts into one atomic save per poll,
redraws result rows only when they change, calculates kill bonuses once, and
limits native-log reads per poll. A backlog schedules another bounded read
promptly; polling slows only after catching up following a terminal result while
the native score screen remains open. These reduce launcher work during the
score transition; native score-screen smoothness still needs gameplay review.

The current plan-21 artifacts passed 72 baseline/maximum configurations across
Casual, Normal and Mental on Miners in the Sun, including starter-camp limits,
basic infantry eligibility, four-faction camps, staged air support and terrain.
Isolated runtime preparations also covered Europeans at Normal/x6 and
USSR, PsiCorps and Guild1 at Mental/x10 with maximum Challenges and Mental AI
Boost. Prepared map/spawn output and private rules/AI preload fields matched
their audited counterparts. Real native-log replay verified result recovery
and receipt deduplication. These checks do not simulate live movement or combat.

The feedback fixes passed **144 terrain-audited configurations**: 108 solo
baseline/helper/maximum variants across every country and difficulty, 24
three-human baseline/maximum variants, and 12 two-human maximum variants.
Isolated Mental/x10 launch preparations for USSR and Last Bastion also passed;
the USSR runtime rules preload contains the actual Drakuv power, provider and
payload. Replaying a retained native victory log counted 1,196 friendly combat
kills after transfer/cash exclusions and reached the 100-point kill cap, while
the original frozen run retained its 35-point local-player bonus. Python
compilation and whitespace checks passed. No player saves or installed source
maps were changed. The full launcher self-check still stops at its existing
RAVA `self_healing_rate` expected-buff mismatch. Native Drakuv delivery, camp
clearance and the relocated camp balance still require ordinary gameplay.

The camp follow-up passed **96 terrain-audited variants**: 72 solo
baseline/maximum variants across all countries and difficulties, plus 24
three-human baseline/maximum variants on Mental. These checks inspect every
actual guard attachment, AND-tag persistence, separate forced ownership,
exactly one crate action, complete hostile-base clearance and serialized
message lengths. Isolated launch preparation also passed with the actual
Pacific and Euro Alliance run settings, both with Mental AI Boost enabled.
Existing version-23 saves still normalize unchanged. The installed native
dispatch was reviewed directly; live combat remains a
separate gameplay check.

The plan-25 pickup changes passed **48 terrain-audited variants**: 24 solo
baseline/maximum variants on Normal and 24 three-human baseline/maximum variants
on Mental, across all twelve countries. These checks verify six independent
startup crate actions, no startup point receipts or clearance messages, human-only
pickup and every reward team's complete frozen unit composition and explicit
arrival waypoint. Isolated launch preparation passed with the saved Pacific and
Euro Alliance settings, including Mental AI Boost. Version-23/24 saved profiles
normalize unchanged and were not edited. Python compilation and whitespace
checks passed. Actual crate pickup and complete native squad arrival still
require a fresh-match gameplay check.

Review camp Area Guard combat/pickups, air targeting and reinforcement behavior
during ordinary gameplay. Keep pending manual checks in [TODOS.md](TODOS.md);
do not open game or launcher windows for routine validation.

A complete 60-minute balance run, all tactical AI situations, long-term frame
rate, and conservative wave-slot release after ordinary mixed combat still need
manual gameplay review. The cap does not bound normal AI armies. Grid's existing
eligibility and unsupported weapon exceptions apply to tier buffs. The full
launcher self-check retains its pre-existing Drakuv/RAVA expected-buff mismatch
(`self_healing_rate`); this feature does not change that contract.
