# Archipelago Integration Architecture

Status: Phases 1-11 complete. The planned integration is implemented,
packaged, and verified against Archipelago 0.6.7.

This directory is the isolation boundary for Archipelago-specific code. The
standalone launcher must not import Archipelago runtime packages during normal
startup. The APWorld is packaged separately and the embedded client will use a
small launcher-facing adapter.

## Existing Randomizer contracts

- `randomizer/application/seed_controller.py` owns deterministic run creation
  and exactly-once check completion.
- `randomizer/application/reward_controller.py` owns reward-pool filtering,
  canonical reward dictionaries, check construction, and earned-reward views.
- `randomizer/maps/progress_hooks.py` injects objective/victory marker teams.
- `randomizer/application/launch_controller.py` tails only appended
  `debug/debug.log` content and forwards a marker to
  `unlock_mission_check(code, check_id, source)`.
- `randomizer/progression/grid.py` owns Grid topology and mission availability.
- `randomizer_state.json` is the crash-safe active-run store. Player YAML and
  portable settings contain next-run options, never progress.
- Generated mission maps apply canonical earned rewards. Archipelago must feed
  this existing history; it must not implement alternate INI mutation logic.

## Integration boundaries

```text
AP server
  |  ws/wss protocol
  v
Archipelago client worker
  |  immutable events through Tk UI queue
  v
Launcher Archipelago controller
  |  received rewards         | completed checks
  v                           v
existing reward history       existing unlock_mission_check
  |                           |
  +---- existing map pipeline +---- LocationChecks packets
```

Only one narrow completion callback should be added after
`unlock_mission_check` has atomically saved state. Objective parsing, victory
reconciliation, manual completion, Grid unlocks, and mission goal evaluation
stay unchanged.

Received AP items are canonical reward names/IDs from the existing reward
catalogue. A persisted, monotonically indexed receipt ledger is the AP
mode earned-reward source. Existing `canonical_reward`, launch filtering,
clone construction, buffs, powers, Unlocks UI, and map generation consume that
source. The client never applies INI rules itself.

## Authoritative run manifest

**Save Player YAML** is one atomic workflow: it reads the visible controls,
saves those launcher settings, generates a fresh AP run, and exports a readable
`launcher_settings` mapping followed by a versioned `run_manifest` JSON block.
Derived catalogue/version fields and unselected generic Archipelago defaults
are omitted. The manifest contains the generated mission order, Grid
coordinates, goal,
campaign selection, reward-slot counts, clean initial server-state snapshot,
frozen reward settings, Randomizer version, and deterministic catalogue
checksum. APWorld validates readable settings against that manifest, creates
its locations, and returns the same required values in `slot_data`.

This avoids copying mission-order/Grid algorithms into the APWorld. On connect,
the launcher validates manifest schema, Randomizer version, catalogue checksum,
and selected-YAML identity before loading the server-returned state snapshot.
AP seed, mission order, Grid, received unlocks, checked locations, mission
completion, and progression then come from server packets, not local run state.
Server item/location placement is not copied into slot data; Archipelago
already owns that data.

Existing `rewards_per_objective` remains the base slot count. The manifest
stores actual already-planned counts per check, preserving the launcher's full
Mission Victory multiplier-bonus formula. No second reward-count algorithm is
implemented in the APWorld.

## Network and persistence contract

- Support compressed `ws` and `wss` WebSockets.
- Request `slot_data` and all item handling flags.
- Read `Connected.slot_info`, request server `DataPackage` names for every
  participating game, and scout only already-completed Mental Omega locations.
  Received items and completed checks therefore retain real player, game,
  item, and source-location provenance without exposing pending placements.
- Persist server seed name, team, slot, received-item index, item receipts, and
  completed location IDs in `randomizer_state.json` under an Archipelago block.
- Treat `ReceivedItems.index == 0` as authoritative full inventory. Any other
  unexpected index requests `Sync`, then resends completed `LocationChecks`.
- Accept repeated items and unattributed/admin-created items.
- Resend completed location IDs after reconnect. Server-side duplicates are
  harmless; local state still rejects duplicate completion effects.
- Send `StatusUpdate` only when existing `is_run_complete()` becomes true.
- Networking runs outside the Tk thread. UI changes cross the existing
  `ui_queue`; no worker reads Tk variables.
- Disconnect stops network synchronization and unlocks controls. It does not
  convert an AP run into a standalone reward plan.

## UI integration

- `randomizer/ui/archipelago.py` owns the top-level `Archipelago` workspace
  tab, connection fields, status, and synchronization log.
- `randomizer/application/archipelago_controller.py` owns UI commands and
  translates worker events through the existing `ui_queue`; it never touches
  Tk from the network thread.
- `WindowController.close_launcher` requests clean client shutdown before Tk
  destruction, except while an active mission keeps the hidden launcher alive.
- Objective reporting reuses the existing completion path and runs only after
  the local check save succeeds. Mission victory reports its reward-slot
  locations plus any objectives completed by existing victory reconciliation.
  Existing `is_run_complete()` alone triggers `StatusUpdate` goal status.
- Slot-data v4 maps each used AP item ID to one exact current Randomizer reward
  name and carries the checksum-verified run manifest plus clean server-state
  snapshot.
  Received rewards replace local check/starting assignments only for an
  AP-enabled run, then flow through existing canonical reward, Unlocks, and map
  pipelines. Standalone reward sourcing remains unchanged.
- Status is red while disconnected, green while connected, and amber during
  connection transitions.
- The activity area remains one normal Archipelago chat feed. Structured
  `PrintJSON` parts resolve through server metadata and render player, item
  classification, location, game, and ordinary text with dark/light-safe
  semantic colors. Item-send packets become one readable
  `finder (game) found item for recipient (game) at location` line;
  synchronization diagnostics remain in the launcher log. Mission details
  list completed placements as item-to-recipient entries plus the sending
  player and exact objective location.
- The Archipelago tab has one **Save Player YAML** action. It never reuses a
  cached manifest or old local run and has no launcher-side YAML load step.
  Export stages only the manifest identity; only a fully validated `Connected`
  event loads server state and promotes it to AP reward sourcing. Disconnect
  restores the latest standalone state/settings; reconnect loads the current
  AP server state again.
- Hosted-room server input defaults and migrates to bare `archipelago.gg`.
  Users copy only the room page's game-server port; browser room URLs are not
  WebSocket endpoints. Custom and localhost hosts remain supported.
- A maintained gameplay-control registry covers Settings, Advanced, and YAML
  mutation controls. Connecting/connected/reconnecting disables the registry
  and connection identity fields; disconnect restores exact prior widget
  states. Disabled controls keep the normal active palette in light and dark
  modes; labels are never disabled. Display/privacy and synchronization-log
  controls remain editable.
- Connection authentication validates the server's full manifest and catalogue
  checksums before tracking begins. Mutable mission state is projected from
  server checked-location packets and refreshed after every server update.

## APWorld packaging

`APWorld/mental_omega/` is the source world folder. Run `build_apworld.ps1` to
create the tracked distributable `Archipelago/mental_omega.apworld`. The resulting archive is
lowercase, contains `mental_omega/` at its root, and excludes Python caches.
Archive entries are path-sorted and use a fixed timestamp, making identical
source trees produce identical `.apworld` bytes.

Archipelago normally injects container compatibility fields through its
source-checkout-only `Build APWorlds` component. The frozen 0.6.7 installer
does not register that component. The local packager therefore reproduces
APWorldContainer v7 metadata in the generated archive while leaving the source
manifest free of container fields.

`build_archipelago_release.ps1` is the complete release entry point. It builds
the one-file Windows launcher and deterministic APWorld, copies the player
setup guide, writes a machine-readable version/hash manifest, and writes
`SHA256SUMS.txt`. The tagged-release workflow publishes all five artifacts;
the player YAML is necessarily generated per run and is not a static release
file.

For normal local packaging, run repository-root `build_all.ps1`. It delegates
to the unchanged focused EXE/APWorld scripts, writes the launcher to the game
root, rebuilds this tracked `.apworld`, and verifies their version contract.
Use `build_archipelago_release.ps1` when the setup guide, release manifest, and
checksums are also required.

## Full APWorld catalogue and manifest

- `generate_catalogue.py` derives a checked-in snapshot from the authoritative
  runtime reward and installed mission catalogues. Published IDs are retained
  across regeneration; the Phase 3 IDs remain unchanged.
- The snapshot contains 3,777 native rewards and 17,640 stable possible
  reward-slot locations across all 97 missions. A SHA-256 checksum covers all
  AP-relevant reward/mission semantics.
- `run_manifest.py` freezes an already-generated launcher run. It counts the
  real rewards produced by existing logic, converts starting rewards to AP
  precollected items, and marks Grid opening rewards as locked-local placements.
  The APWorld validates and shuffles this data; it does not copy reward RNG.
- Mission regions are AP-reachable because mission unlocking remains local
  Randomizer state. Runtime victory comes from the client's native goal report;
  a private event exists only for AP fill beatability.

## Verified Phase 3/4 smoke baseline

- Archipelago 0.6.7 loads the packaged world as Mental Omega v0.2.0.
- Official generation completes with two progression items, two network
  locations, and the private victory event in a later logic sphere.
- The generated archive starts in ArchipelagoServer 0.6.7 and exposes the
  embedded Mental Omega data package.
- `client/handshake.py` connects to that server with compressed WebSockets,
  authenticates the generated `MOSmoke` slot, and validates returned slot data.
- The refusal path recognizes `InvalidSlot`.
- `client/session.py` owns a daemon worker with exponential reconnect, clean
  stop, outbound check/chat/status commands, reconnect check resend, `Sync`
  recovery, room updates, and server messages.
- `client/ledger.py` keys every receipt by AP item index, preserves repeated
  identical rewards, accepts gap packets while requesting resynchronization,
  and serializes acknowledgment state for crash-safe integration.
- Real-server audits passed two check/item receipts, checkpoint restoration
  without duplicate item delivery, goal status 30, and automatic reconnection
  across a killed/restarted server using the same worker.
- The real Tk tab connected, displayed authenticated status through
  `ui_queue`, disconnected, and left no worker behind.
- The Phase 5 controller maps each successful non-victory objective to all of
  its `slot_data` location IDs, persists offline completion, reconciles after a
  validated reconnect, and deduplicates repeats. A real 0.6.7 server received
  Allied 01 Objective 1 location 81129472 exactly once and returned its placed
  item receipt.
- Phase 6 reuses the same saved victory path for debug-log and manual
  completion. A real 0.6.7 server audit reported Allied 01 objective and
  mission-completion locations 81129472–81129473, received both items, emitted
  server goal status, and rejected a duplicate report. Grid goal completion in
  an AP-enabled run unlocks optional missions without releasing their unchecked
  locations; standalone release behavior remains unchanged.
- Phase 7 persists each received reward record before acknowledging its AP
  receipt index. A failed first save leaves the item pending; a crash between
  reward save and acknowledgment recovers the acknowledgment without applying
  twice. A live 0.6.7 full-mission audit applied `Soviet Conscript Access` and
  `GI Access`, acknowledged indexes 0–1, preserved goal completion, and exposed
  both through the existing earned-reward/launch-rule pipeline.
- Phase 8 APWorld v0.3.0 loaded in official frozen Archipelago 0.6.7 with 3,776
  items and 17,640 locations. A full 97-mission Grid manifest generated 5,340
  active locations/items (six locked-local opening rewards and 5,334 shuffled
  items) in 0.65 seconds. A live schema-3 server/client audit matched both
  checksums, synchronized two location rewards, and acknowledged all 14
  received records. AP-received hostile-AI rewards use existing enemy scaling
  instead of stale local assignments.
- Source and one-file launcher self-checks verify `websockets==17.0` and the
  client contract. Normal GUI startup does not import that dependency.
- Phase 11 used an official generated one-mission room with six objective and
  twelve victory reward slots. A real 0.6.7 server was killed/restarted under
  a live session; the client reconnected, restored all checks, and redelivered
  zero acknowledged items. Two client checkpoint restorations likewise
  redelivered zero items. One hundred duplicate objective reports plus one
  hundred duplicate victory reports sent no duplicates; all 18 items were
  received and acknowledged once, and repeated goal completion was rejected.
  Focused real-launcher completion audits confirmed standalone objectives and
  victory earn the local 6/18 rewards, while AP mode earns zero local rewards,
  persists all 18 locations offline, and persists goal completion.

## Completed integration boundary

Future changes should extend these contracts rather than replacing existing
controls. Do not duplicate the full AP catalogue or placement algorithms in
the launcher.
