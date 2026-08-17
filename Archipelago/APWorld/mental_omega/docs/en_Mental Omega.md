# Mental Omega

Mental Omega Randomizer launches campaign missions, detects objective and
victory checks through its existing debug-log hooks, and applies received
technology and buff rewards to later generated mission maps.

This APWorld uses a checksum-protected run manifest exported by Mental Omega
Randomizer 1.28. It supports 3,833 rewards and 35,876 stable possible
reward-slot locations across the full 97-mission catalogue. Each seed activates
only the locations and item counts described by its manifest.

Mission regions follow signed local progression logic. Mission List and
Classic use victory-count requirements; Grid Mode uses exact starting nodes
and orthogonal neighbors. One locked `Local Victory` marker per mission makes
that local progress visible to Archipelago's sphere calculation without
shuffling mission-unlock items or changing launcher mission availability.
