## BUGS AND IMPROVEMENTS

- [x] Prevent Enemy Powerhouses from copying authored object/death tags to bonus teams or expanding tagged story teams; audit the real Hamartia replacement/Irkalla callbacks across campaign modes and enforce the same rule in co-op audits.
- [ ] Confirm the reported visual unit replacement after death during normal gameplay. No original report map/replay exists; the confirmed Powerhouses death-trigger leak is fixed, but the exact Kirov-to-Apocalypse observation remains unverified.

Fortress mode
- [x] Disable campaign challenge-map inclusion in Final Fortress Settings and show a Fortress-only 2/3-player selector shared with its connection dialog, keeping campaign co-op preferences separate.
- [x] Add two/three-human Fortress co-op over the authenticated ZeroTier lobby, shared host perks, individual Defensive Points/purchases and human-first friendly seat allocation (2 humans + at most 1 AI; 3 humans + no AI).
- [ ] Verify two/three-PC ZeroTier Fortress gameplay, shared objective victory/defeat, guest point persistence, human camp pickups and disconnect behavior during the next normal multiplayer session. No game windows opened for routine validation.
- [x] Rename Final Fortress currency to Defensive Points throughout the launcher, in-game camp messages and documentation while preserving existing saves and Shop Mode Gems.
- [x] Show a Final Fortress run results screen after victory or defeat, including total Defensive Points and the sources of each reward.

PERKS
- [x] Faster production speed which can be improved 5 times and get more expensive with each purchase
- [x] Starting units up to 15 at the start, get 3 per Perk point, each perk point gives more advanced units aswell starting with T1 up to T3 at the end and 1-2 special units depending on the faction
- [x] Get Perk with extra starting buildings, each perk starts with one Powerplant, then barracks, then refinery, then radar, then war factory
- [x] Get Perk that starts with defensive structures around the base, each perk gives next to the base defense the next one and until Tier 3 ones (e.g. sentry gun, then AA gun, tesla tower, hammertower)
- [x] Get Perk with veteran defenese
- [x] Buff defenses through six ranks: +10% damage, fire rate and range per rank, up to +60%.
- [x] Buff player/allied units separately for Tiers 1–3 through six ranks: +5% health, damage and fire rate per rank, up to +30%, using isolated copies and increasing prices.
- [x] Add Perk which gives cloned support powers from faction. (This would need to be determined per faction then)
- [x] Add Perk which reveals the entire map immediatly
- [x] Add Perk which allows up to two allied helpers, they will just be normal skirmish AI's BUT with the buffs/perks the player also has

Fortress gameplay review (implementation uses provisional configurable values)
- [x] Bind enemy wave/controller reinforcement actions explicitly to their spawn waypoints; audit the emitted action arguments and reject enemy arrival aprons near friendly bases or detached from their own starts.
- [ ] Confirm reported enemy waves appearing inside the player base no longer occur during the next normal gameplay session, including ground and flying batches. No game windows opened for routine validation.
- [x] Give the nearby north-east starter camp a separate basic-infantry pool, smaller difficulty-scaled counts and low multiplier caps while retaining its normal rewards; keep outer camps tougher.
- [ ] Review early resource access with no starting-army/defense perks on Casual and Normal during the next ordinary gameplay session. No game windows opened for routine validation.
- [x] Restrict the all-unlocks Testing profile to an existing ignored save in a local source checkout; compiled EXEs expose Standard only and reject testing initialization.
- [x] Verify infantry in saved wave rosters; expand ground stages to four alternatives and add staged faction air attacks from minutes 15/30 within the existing shared wave budget.
- [x] Separate flying and ground wave teams, preserving infantry and selected Powerhouse identities and existing slot release tracking.
- [ ] Review actual faction air arrivals, targeting and mixed-wave balance during the user's next normal run; no game windows opened for routine checks.
- [x] Select camp rosters independently of enemy bases, guaranteeing Allies, Soviets, Epsilon and Foehn across the six camps in every new run.
- [x] Fix the native-log checkpoint to retain only 64 bytes before the cursor, drain backlog after process exit, and recover verified unfinished outcomes with an original-save backup and deduplicated receipts.
- [x] Recover the reported Testing victory from the retained native log: both milestones, four logged camp claims and kill tiers; credit 250 missing Defensive Points, bringing the balance to 455.
- [x] Award camp Defensive Points on clearance independently of random crate collection; show cleared/uncollected camps in results.
- [x] Scale camp guards by difficulty and wave multiplier, using varied owning-faction infantry/vehicle/artillery rosters and occasional heroes/heavies, with configurable per-camp/shared ceilings and thirty reviewed positions per camp.
- [ ] Confirm new camp formation variety, clearance Defensive Points messages, separate crate collection and complete victory receipts during the user's next normal gameplay session. No game windows opened for routine validation.
- [x] Replace whole friendly-arrival reservations with small reusable groups shared across the existing cap, independent human/helper delivery timers and an on-screen capacity-wait notice.
- [x] Spawn friendly reinforcements at the center of their existing protected 5x3 arrival aprons.
- [x] Add a separate Next enemy wave countdown that resets with actual deliveries and stops after the final wave/run outcome, preserving Until Victory.
- [ ] Confirm friendly deliveries resume after capacity returns and the new wave countdown displays, resets and disappears correctly during the user's next normal play session. Do not open game windows for routine checks.
- [x] Replace whole-enemy-wave reservations with reusable groups of at most twenty, keeping the shared 480-unit ceiling and ordered five-minute wave intervals.
- [x] Reserve separate walkable enemy arrival aprons so wave units cannot spawn inside construction yards or later buildings.
- [x] Exclude immortal enemy buildings/MCVs/defenses from legal targeting; redirect private helper building-only assaults to hostile legal targets.
- [x] Add the installed Mental AI Boost option to Fortress Defense setup, saved per profile and applied to enemy/helper AI and their cloned factories.
- [ ] Confirm continued enemy wave deliveries, unobstructed arrivals and helper targeting during the user's next normal play session, with Mental AI Boost off/on as desired. No game windows opened for routine checks.
- [x] Extend periodic reinforcements with rank 7 Veteran and rank 8 Elite arrivals, retaining the full rank-6 roster, timing and shared cap.
- [x] Remove the primary-enemy-only targeting restriction from trigger-created Fortress teams, matching installed AI teams and allowing helpers to acquire all hostile houses.
- [x] Move friendly perk defenses to outer approach batteries, with the human layout following the marked front/right area and complete foundation/terrain/bounds checks.
- [ ] Confirm actual Veteran/Elite arrival pips, helper starting/reinforcement movement and outer defensive coverage during the next user gameplay session; no game windows opened for routine checks.
- [x] Add Challenge multi-selection with drag, Shift/Ctrl/Alt, Select all/Ctrl+A, and atomic bulk enable/disable/max-stack actions.
- [ ] Review Challenge range selection, additive selection, group toggles and bulk Max stacks during the next launcher session; no visible windows opened for routine validation.
- [x] Apply the "Until Victory" caption after Timer Set/Start; native Timer Set cleared the previous text. Audit actual action order and duration.
- [x] User screenshot confirms the corrected Until Victory caption is visible.
- [x] Replace prerequisite overrides with gated alternative lists to prevent duplicate native/private Harrier production.
- [x] Reserve walkable 5x3 reinforcement aprons against construction when periodic reinforcements are enabled.
- [x] Give helper starting armies and periodic arrivals explicit attack teams instead of relying on recruitment of unique tracking types.
- [x] Show actual periodic income totals in perk rank descriptions (Purifier: 25/30/35/40 credits; base 20).
- [ ] Confirm one Harrier icon, building rejection on reserved arrival tiles, continued arrivals and helper attack orders during the user's next gameplay session. Do not open game windows for routine validation.
- [x] Relocate starting defenses and power plants inside playable LocalSize and validate complete foundations/elevation before launch.
- [x] Add concrete native unit faction gates, preventing foreign Virus production for Euro Alliance.
- [x] Correct starting-army Veteran/Elite object experience from 1/2 to 100/200.
- [x] Spread six camps across clear playable map regions and start their guards asleep before garrison recruitment.
- [x] Give each enemy a protected construction-yard start, indestructible base construction, and 24 fixed power-independent anti-rush defenses; route AI production/docking through private copies.
- [ ] Confirm corrected ranks, six camp locations and clear/claim behavior, enemy construction-yard starts, ongoing production and immunity during the user's next gameplay session. Do not launch the game for routine checks.
- [ ] Review Defense Armor Challenge balance now that constructed enemy defenses are indestructible.
- [x] Add Automatic healing, Sight and stealth detection, Unique-unit capacity, and Special building income as ranked player/helper perks using existing reward adapters.
- [x] Add Powerhouses, Paratroopers, Bloodhounds, Moon reinforcements and faction offensive superweapons as opt-in enemy Challenges, with provisional victory bonuses and finite reinforcement-power launch budgets.
- [ ] Confirm new healing/sensors/capacity/income effects and enemy power charging, targeting, payloads and finite launch counts during the user's next gameplay session; do not open game windows for routine checks.
- [x] Add ranked special-unit production access: one additional reviewed faction unit per point, retaining unique build limits.
- [x] Add six-rank friendly reinforcements every five minutes with a separate shared 150-unit living cap, delayed admission, and the same grants for helpers.
- [ ] Confirm native special-unit production, conversion/art, friendly arrival placement and cap waiting during the user's next gameplay session; no game windows opened for source audits.
- [x] Add secondary faction superweapons at rank 1, retain them alongside offensive weapons at rank 2, and extend Supply cache to six ranks.
- [x] Provide a separate all-unlocks testing profile selectable in the Fortress header; confirm production speed affects every unit and building queue.
- [ ] Confirm secondary powers and private Nanofiber transformations during the user's next gameplay session; do not open game windows for verification.
- [x] Put Challenge arrows inside each row beside Stacks; remove the perk horizontal scrollbar and the second vertical scrollbar.
- [x] Add primary faction superweapons and a six-rank perk applying compatible Grid/Shop power upgrades to unlocked perk powers.
- [x] Replace Apply stacks with immediate left/right controls and Max stack; keep rank effects in a themed side panel without reducing perk-list height.
- [x] Add Elite as the second starting-army veterancy rank, and five cumulative faction support-power unlocks.
- [ ] Review the revised panel layout and newly unlocked support powers during the next user gameplay session; generated-map audits pass without opening the game.
- [x] Double-click Challenge rows to toggle modifiers; show cumulative faction-specific effects for every perk rank without repeating prices.
- [x] Give four of each unlocked starting defense around the base, plus enough faction power plants for the granted structures.
- [x] Label the survival countdown "Until Victory" and reduce redundant result-screen saves/redraws.
- [ ] Confirm the timer caption, expanded defense layout and native score-screen smoothness in a future gameplay session; source/terrain checks pass without opening the game.
- [ ] Confirm the latest camp garrison holds position, wakes on player attack, and releases its crate after clearing. Do not launch fullscreen or repeatedly open the game for checks.
- [ ] Tune perk prices, helper balance and the 480 scripted-unit ceiling during a full 60-minute survival run.

Possible future perks (suggestions, not implemented)
- Remaining player perk ideas using existing reward adapters: cheaper production, weapon range, aircraft ammunition, transport seats/open-topped fire, mind-control capacity, and harvester storage. Each requires eligible-target selection and Fortress integration.
- Emergency repair of Einstein's Lab, limited to once per run.
- A reserve reinforcement squad triggered when the Lab reaches low health.
- A choice between two camp crate rewards instead of receiving one random reward.



## INFO

To use Phobos add dll and edited ini
