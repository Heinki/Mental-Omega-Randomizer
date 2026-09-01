# Mental Omega

Mental Omega Randomizer launches campaign missions, detects objective and
victory checks through its existing debug-log hooks, and applies received
technology and buff rewards to later generated mission maps.

This APWorld uses a checksum-protected run manifest exported by Mental Omega
Randomizer 1.33. It supports the full 97-mission reward catalogue plus stable
Shop purchase, stage-reward, and private stage-logic IDs. Each seed activates
only the locations and item counts described by its manifest.

Mission regions follow signed local progression logic. Mission List and
Classic use victory-count requirements; Grid Mode uses exact starting nodes
and orthogonal neighbors. One locked `Local Victory` marker per mission makes
that local progress visible to Archipelago's sphere calculation without
shuffling mission-unlock items or changing launcher mission availability.

Shop Mode uses a signed eligible mission pool and a ten-stage marker chain.
Each local victory advances one stage, can release a shuffled
`Shop Run Mission N Victory` location, and completion of the full run satisfies
the goal. The launcher can also spend persistent Gems on generated
`Roguelike Shop Purchase N` locations. Those purchases never request an item;
Archipelago fill decides the recipient and item normally. Every received AP
unit unlock is active in every run without consuming permanent extra-unit
slots; received buffs and powers are also reapplied. This signed restart policy
never changes mission credits, Ore, or Gems.
