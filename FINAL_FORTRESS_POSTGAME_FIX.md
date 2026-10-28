# Final Fortress post-game progression and kill rewards

## Findings

The reported `Run plan contains unpurchased perk ranks.` error came from
validating a completed run's frozen ranks against the player's current
purchases. Refunding a rank after victory made that historical comparison
fail. Commit `2f08a15` already restricts this check to active local runs. That
fix is retained in this candidate; historical plans and receipts are not reset.

The missing kill rewards have a separate cause. The color selector swaps the
host's default Teal with the selected color in native spawn settings, but the
score parser still expected the original schemes. Aqua uses native scheme 7,
while the host's frozen roster records scheme 1. The parser required every
friendly score to match before accepting any counters, so this mismatch
prevented kill rewards even with a verified victory.

Score matching now applies the same palette swap, including a helper or guest
that previously held the selected color. Frozen plans remain unchanged, so
existing saves continue to validate and retained native logs can recover missed
rewards through the existing recovery workflow. Empty legacy counters also
report missing scores instead of claiming that no threshold was reached.

Auditing selected co-op colors found an additional launch error: the co-op
spawner called the solo spawner, which tried to reorder the human roster while
only `Commander` existed. The co-op adapter now builds the base without applying
colors and applies them once after all human and helper entries exist.

## Verification

- Python compilation and `git diff --check` passed.
- All eight retained local Fortress profile/backup documents normalized.
- Installed The Sky Mountain map audits passed for all twelve countries at
  easy difficulty: Aqua solo baseline and helpers (24 configurations), Purple
  two-human co-op with a helper (12), and Yellow three-human co-op (12).
  The audit independently compares emitted native house colors with installed
  `uimd.ini` and rules `[Colors]` entries. Co-op audits also verify all peer
  settings and color-ordered human spawn locations.
- Replaying actual retained victory and defeat logs against copies of their
  original profiles recovered 399 and 224 player combat kills respectively.
  Victory recovery added 250 missing points. Replaying either log again made
  no changes and awarded no further points; frozen plans stayed identical.
- On copies of real abandoned and recovered-victory profiles, refunding Defense
  firepower from rank 6 to 5 saved and reloaded while history kept rank 6.
  Repurchasing restored the original wallet and rank without changing history.
- The Windows launcher built successfully. Its packaged installation report
  passed against this installation, including static configuration validation.
  The local candidate is `../MentalOmegaRandomizer-FortressFix.exe`; no release
  was published and the installed default launcher was not replaced.

Audit maps, replay copies, reports and build logs are under
`/tmp/final-fortress-fix/`. Native gameplay was not run for this change.

## Report limitations

The pasted attachment ends inside the run configuration with
`... (787 KB left)`. It is not a complete JSON document and contains neither
the frozen run plan nor final native kill statistics. The player's exact
missing reward cannot be reconstructed from this attachment. Automatic
recovery requires the matching run's START, result markers and score table in
`debug/debug.log`; a save alone cannot establish the missing kills.
