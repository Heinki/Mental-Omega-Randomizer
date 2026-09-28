## BUGS AND IMPROVEMENTS

### Co-op mode: 6 remaining work packages

Local host and guest games start. The shared Grid, co-op map pool, direct-IP
pairing setup, and provisional co-op Shop mission offers exist. Shop map
generation now creates country-gated host and guest unit clones; both local
game copies reached gameplay. A temporary game trigger confirmed the victory
marker appears in the real debug log. Shop Mode now exposes the co-op checkbox,
separate runs, host-controlled mission choices, and direct game launch. Local
Shop stage and pairing checks pass; a full co-op Shop mission still needs a
player playtest. The direct command-line diagnostic also exchanges private
unit loadouts and rejects mismatched seed or stage. Closing a Shop co-op game
without a host victory marker now records one failure on each player's private
run; host Emergency Revival decides whether both runs revive. Local failure and
duplicate-message checks pass.

- [ ] Play and win a full co-op mission; verify automatic host completion,
      guest sync, loss, disconnect, and replay behavior.
- [ ] Verify earned units and buffs in both live games, including build menus
      and synchronized combat.
- [ ] Add co-op effects still missing from single-player parity: earned powers,
      buildings, starting credits, enemy scaling, and production restrictions.
- [x] Sync one host-controlled Shop stage: co-op mission offers, selection,
      commitment, rerolls, difficulty assist, and launch. Validated lobby
      snapshots, guest acknowledgement, separate run files, and UI flow exist.
- [x] Keep each player's Shop profile, Ore, purchases, buffs, and upgrades
      separate; exchange validated supported unit access and buff loadout
      snapshots from the launcher before launch. Other in-game reward effects
      remain in the parity task above.
- [ ] Enforce different host and guest loadouts in the same generated map;
      verify sidebar access and buffs in a live game. Country-gated clone
      generation and local game startup are implemented.
- [x] Apply host victory and close-without-victory failure to each Shop run
      separately. Host Emergency Revival controls both stage outcomes; repeat
      failure messages do not repeat the transaction. Local checks pass.
- [ ] Recover both Shop runs after a lobby disconnect, including a result
      missed while disconnected. Verify victory, failure, rewards, revival,
      and replay in a full co-op mission on two live games.
- [ ] Test two real PCs on LAN, ZeroTier, and forwarded public IPv4; package
      and document verified setups.

## INFO

To use Phobos add dll and edited ini
