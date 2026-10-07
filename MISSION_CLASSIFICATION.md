# Mission Build Classification

This is the community-reviewed three-way classification used by seed generation:

- `base_build`: the player owns, receives, captures, or operates a normal base.
- `true_no_build`: fixed/scripted units, heroes, or map powers with no player production.
- `no_build_production`: no normal base-building phase, but limited unit production is available.

The launcher provides separate inclusion settings for the two no-build categories.
Turning both off creates a build-only mission pool. Allied 01 remains explicitly
classified as `base_build`.

Optional APRA2 catalogue entries add 30 missions: 23 `base_build`, two
`true_no_build`, and five `no_build_production`. Their exact `A01`-`A12`,
`S01`-`S12`, `ACO1`-`ACO3`, and `SCO1`-`SCO3` mappings live in
`configs/missions.json`; standard Mental Omega installations keep this 97-map
table unchanged.

| Mission ID | Installed mission | Classification |
|---|---|---|
| `AREDDAWN` | Allied 01: RED DAWN RISING | `base_build` |
| `AEAGLESFLY` | Allied 02: EAGLE FLY FREE | `base_build` |
| `AROADTRIP` | Allied 03: ROAD TRIPPIN' | `no_build_production` |
| `AHEAVENHELL` | Allied 04: HEAVEN AND HELL | `base_build` |
| `ABADAPPLE` | Allied 05: BAD APPLE | `no_build_production` |
| `ABMIND` | Allied 06: BEAUTIFUL MIND | `base_build` |
| `AHAMMERFALL` | Allied 07: HAMMER TO FALL | `true_no_build` |
| `AWRONGSIDE` | Allied 08: WRONG SIDE | `true_no_build` |
| `AZEROSIGNAL` | Allied 09: ZERO SIGNAL | `no_build_production` |
| `AGARDENER` | Allied 10: THE GARDENER | `true_no_build` |
| `APANIC` | Allied 11: PANIC CYCLE | `base_build` |
| `ASUNLIGHT` | Allied 12: SUNLIGHT (Finale) | `base_build` |
| `ASIREN` | Allied 13: THE MERMAID | `true_no_build` |
| `APUPPET` | Allied 14: PUPPET MASTER | `base_build` |
| `ASTONE` | Allied 15: STONE COLD CRAZY | `no_build_production` |
| `AGHOST` | Allied 16: GHOST HUNT | `base_build` |
| `ABOTTLE` | Allied 17: BOTTLENECK | `true_no_build` |
| `AHYST` | Allied 18: HYSTERIA | `base_build` |
| `ASTORM` | Allied 19: STORMBRINGER | `base_build` |
| `APARA` | Allied 20: PARANOIA | `true_no_build` |
| `ARELE` | Allied 21: RELENTLESS | `base_build` |
| `AINSOMNIA` | Allied 22: INSOMNIA | `base_build` |
| `AWITHER` | Allied 23: WITHERSHINS | `base_build` |
| `AHAMARTIA` | Allied 24: HAMARTIA (Finale) | `base_build` |
| `SBLEED` | Soviet 01: BLEED RED | `base_build` |
| `SGGATE` | Soviet 02: GOLDEN GATE | `no_build_production` |
| `SHBD` | Soviet 03: HAPPY BIRTHDAY | `base_build` |
| `SSIDE` | Soviet 04: SIDE EFFECT | `base_build` |
| `SPEACE` | Soviet 05: PEACE TREATY | `no_build_production` |
| `SRECH` | Soviet 06: RECHARGER | `true_no_build` |
| `SIDLE` | Soviet 07: IDLE GOSSIP | `base_build` |
| `SDEATH` | Soviet 08: DEATH FROM ABOVE | `base_build` |
| `SROAD` | Soviet 09: ROAD TO NOWHERE | `no_build_production` |
| `SOPEN` | Soviet 10: THE LUNATIC | `true_no_build` |
| `SMACHINE` | Soviet 11: UNSHAKEABLE | `base_build` |
| `SDRAGON` | Soviet 12: DRAGONSTORM (Finale) | `base_build` |
| `SRAVEN` | Soviet 13: THE RAVEN | `base_build` |
| `SAWAKE` | Soviet 14: AWAKE AND ALIVE | `true_no_build` |
| `SEXIST` | Soviet 15: EXIST TO EXIT | `base_build` |
| `SFIRE` | Soviet 16: FIREWALKING | `base_build` |
| `SJUGGER` | Soviet 17: JUGGERNAUT | `base_build` |
| `SHEART` | Soviet 18: HEARTWORK | `true_no_build` |
| `SRED` | Soviet 19: POWER HUNGER | `base_build` |
| `STHREAD` | Soviet 20: THREAD OF DREAD | `base_build` |
| `SMELT` | Soviet 21: MELTDOWN | `no_build_production` |
| `SEARTH` | Soviet 22: EARTHRISE | `base_build` |
| `SFATAL` | Soviet 23: FATAL IMPACT | `base_build` |
| `SHAND` | Soviet 24: DEATH'S HAND (Finale) | `base_build` |
| `EPEACE` | Epsilon 01: PEACEKEEPER | `true_no_build` |
| `EACCEL` | Epsilon 02: ACCELERANT | `true_no_build` |
| `ESCRAP` | Epsilon 03: SCRAPYARD | `no_build_production` |
| `ESHIP` | Epsilon 04: SHIPWRECKED | `base_build` |
| `EHUMAN` | Epsilon 05: HUMAN SHIELD | `true_no_build` |
| `ELAND` | Epsilon 06: LANDLOCKED | `true_no_build` |
| `ETHINK` | Epsilon 07: THINK DIFFERENT | `base_build` |
| `ELORD` | Epsilon 08: WARRANTY VOID | `no_build_production` |
| `EFIELDS` | Epsilon 09: KILLING FIELDS | `true_no_build` |
| `EFOCUS` | Epsilon 10: FOCUS SHIFT | `true_no_build` |
| `ESING` | Epsilon 11: SINGULARITY | `true_no_build` |
| `EMOON` | Epsilon 12: MOONLIGHT (Finale) | `base_build` |
| `EDILEMMA` | Epsilon 13: THE CONQUEROR | `base_build` |
| `EHUEHUE` | Epsilon 14: HUEHUECOYOTL | `true_no_build` |
| `EBREED` | Epsilon 15: MEMORY DEALER | `base_build` |
| `EDIVER` | Epsilon 16: DIVERGENCE | `base_build` |
| `EGODSEND` | Epsilon 17: GODSEND | `no_build_production` |
| `ELIZARD` | Epsilon 18: LIZARD BRAIN | `no_build_production` |
| `EBLOOD` | Epsilon 19: DANCE OF BLOOD | `base_build` |
| `EHEAD` | Epsilon 20: MACHINEHEAD | `true_no_build` |
| `ESANDS` | Epsilon 21: OBSIDIAN SANDS | `base_build` |
| `ETOTAL` | Epsilon 22: UNTHINKABLE | `base_build` |
| `EREALITY` | Epsilon 23: REALITY CHECK | `true_no_build` |
| `EMIGDAL` | Epsilon 24: BABEL (Finale) | `base_build` |
| `FNOBODY` | Foehn 01: NOBODY HOME | `true_no_build` |
| `FKILL` | Foehn 02: KILL THE MESSENGER | `base_build` |
| `FEMPIRE` | Foehn 03: TAINTED EMPIRE | `no_build_production` |
| `FBEYOND` | Foehn 04: THE GREAT BEYOND | `base_build` |
| `FPOINT` | Foehn 05: VANISHING POINT | `true_no_build` |
| `FREMNANT` | Foehn 06: THE REMNANT (Finale) | `base_build` |
| `ADEMON` | Allied Op: DIGITAL DEMON | `no_build_production` |
| `AOBST` | Allied Op: OBSTINATE | `base_build` |
| `ACONV` | Allied Op: CONVERGENCE | `true_no_build` |
| `AFULL` | Allied Op: FULLMETAL | `base_build` |
| `AGRID` | Allied Op: GRIDLOCK | `base_build` |
| `ASOMNIA` | Allied Op: PARASOMNIA | `base_build` |
| `SARCHE` | Soviet Op: ARCHETYPE | `true_no_build` |
| `SECLIPSE` | Soviet Op: ECLIPSE | `base_build` |
| `STROPH` | Soviet Op: TROPHY HUNTER | `no_build_production` |
| `SNOISE` | Soviet Op: NOISE SEVERE | `no_build_production` |
| `SDAWN` | Soviet Op: DAWNBREAKER | `base_build` |
| `SARMS` | Soviet Op: BROTHERS IN ARMS | `base_build` |
| `ETACI` | Epsilon Op: TACITURN | `true_no_build` |
| `EASHES` | Epsilon Op: FALLEN ASHES | `no_build_production` |
| `ERAGE` | Epsilon Op: BLOOD RAGE | `true_no_build` |
| `ESPLIT` | Epsilon Op: SPLIT SECONDS | `base_build` |
| `ENIGHT` | Epsilon Op: NIGHTCRAWLER | `no_build_production` |
| `ESURV` | Epsilon Op: SURVIVORS | `no_build_production` |
| `FCAPSULE` | Foehn Op: TIME CAPSULE | `true_no_build` |

Foehn Op: TIME CAPSULE remains a true no-build mission, but seed ordering treats
it as a late Foehn mission because of its difficulty. Only Foehn 01 and 05 are
allowed into protected opening positions while alternatives exist.


## Cooperative missions

The 36 installed two-player co-op maps use the same independent inclusion
settings. Classifications live in `configs/missions.json` under
`coop_build_classifications`, separately from campaign reward tiers.

These entries follow the installed maps: scripted human MCVs and transferred
Construction Yards count as base building; fixed or capturable production
without a normal base phase counts as limited production. `DMCV` is a hidden
mission actor and does not count as a playable Construction Yard.

| Mission ID | Installed mission | Classification |
|---|---|---|
| `COOP_ABALANCE` | Allied Op: Balance of Power | `no_build_production` |
| `COOP_ABLUT` | Allied Op: Blut Royale | `true_no_build` |
| `COOP_ABUGGY` | Allied Op: Attack on Buggy | `no_build_production` |
| `COOP_ADOWNFALL` | Allied Op: Downfall | `base_build` |
| `COOP_AENFO` | Allied Op: Enforcers | `base_build` |
| `COOP_AHYPO` | Allied Op: Hypothermia | `base_build` |
| `COOP_ALA` | Allied Op: Low Rider | `base_build` |
| `COOP_AMONSTER` | Allied Op: Mad Monster | `no_build_production` |
| `COOP_APANZER` | Allied Op: Panzer Ace | `true_no_build` |
| `COOP_APWAR` | Allied Op: Impersonal War | `base_build` |
| `COOP_ASARIN` | Allied Op: Good Old Times | `true_no_build` |
| `COOP_ATECH` | Allied Op: Technologic | `true_no_build` |
| `COOP_ECARD` | Epsilon Op: The Cardinal | `base_build` |
| `COOP_ECOR` | Epsilon Op: Metaphor | `base_build` |
| `COOP_EJEAL` | Epsilon Op: Backbitten | `base_build` |
| `COOP_ELIES` | Epsilon Op: Television Lies | `true_no_build` |
| `COOP_EMIND` | Epsilon Op: Mind Over Matter | `base_build` |
| `COOP_EMONO` | Epsilon Op: Monochromatic | `base_build` |
| `COOP_ENECRO` | Epsilon Op: Neuromancers | `base_build` |
| `COOP_EPAIN` | Epsilon Op: Brain Reset | `true_no_build` |
| `COOP_ERAIN` | Epsilon Op: Rainmaker | `true_no_build` |
| `COOP_ERETAL` | Epsilon Op: Retaliation | `base_build` |
| `COOP_ERUSH` | Epsilon Op: Rush Tactics | `base_build` |
| `COOP_ESTROKE` | Epsilon Op: Research Stroke | `base_build` |
| `COOP_SBURNED` | Soviet Op: Burned Alive | `true_no_build` |
| `COOP_SCOMB` | Soviet Op: Combustion | `base_build` |
| `COOP_SCYBER` | Soviet Op: Cyberanatomy | `base_build` |
| `COOP_SEGO` | Soviet Op: Ego Ergo Hax | `true_no_build` |
| `COOP_SLIGHTS` | Soviet Op: Lights Out | `base_build` |
| `COOP_SNEEDLE` | Soviet Op: Needlehead | `base_build` |
| `COOP_SRAVAGE` | Soviet Op: Ravages of War | `base_build` |
| `COOP_SREPEN` | Soviet Op: Repentance | `base_build` |
| `COOP_SROLE` | Soviet Op: Role Reversal | `true_no_build` |
| `COOP_SSOURCE` | Soviet Op: Money Source | `base_build` |
| `COOP_STHUNDER` | Soviet Op: Thunder God | `base_build` |
| `COOP_STOXIC` | Soviet Op: Intoxicated | `base_build` |
