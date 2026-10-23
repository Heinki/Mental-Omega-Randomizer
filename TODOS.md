## BUGS AND IMPROVEMENTS

Implemented Fortress perks (new runs; native gameplay confirmation pending)

- Lab durability: permanent ranks cost 5 / 10 / 20 Defensive Points and give +25% / +50% / +100% maximum health (1,500 / 1,800 / 2,400 HP). Each rank replaces the previous bonus. The Lab starts full; emergency repair restores the upgraded maximum. Co-op applies the host's rank once to the shared objective. Requires a new plan-28 run.
- Emergency Lab repair: 10 Defensive Points, one automatic full repair per run at the native red-health transition (35% in Mental Omega). The editor's "quarter health" event actually follows ConditionRed, so global balance remains unchanged instead of forcing 25%.
- Lab reserve squad: 15 Defensive Points, once per run below 50% Lab health; immediately protect only the Lab with 10 in-game seconds of Iron Curtain while 3 faction infantry and 1 basic vehicle arrive per friendly house. A red-health fallback handles hits that skip the half-health event. Human squads remain controllable; periodic reinforcement capacity does not delay this finite reserve. The shield is included in the reserve purchase and needs a new plan-27 run.
- Manual checks: damage the Lab across both thresholds, including hits landing exactly on a threshold and a large hit crossing both; verify full repair, complete reserve arrivals, immediate Lab-only protection for 10 in-game seconds, no shield on nearby enemies/friendlies, no second activation after further damage/healing, normal damage after shield expiry, normal defeat after the repair is spent, and shared one-use behavior with two/three humans. Compare reserve alone and both perks enabled, including emergency repair during the shield. Do not assume this prevents an already lethal hit.
- Durability gameplay checks: verify 1,500 / 1,800 / 2,400 maximum HP at ranks 1–3, full starting health, full upgraded emergency repair, unchanged percentage-based reserve/repair thresholds, and no extra multiplier from co-op/helper count. Disabling durability should restore 1,200 HP in the next run.



## INFO

To use Phobos add dll and edited ini
