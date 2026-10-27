# Release verification: MO, DTA, and Reloaded

Checked the working release candidates on 27 October 2026 against the actual installed games. The requested functional checks passed after the fixes below. This is startup and configuration verification, not certification of complete campaigns or multiplayer sessions.

## Coverage

| Check | MO 1.45 | DTA 2.3 | Reloaded 1.8 |
| --- | --- | --- | --- |
| Installed campaign catalogue | 97 missions | 93 missions | 108 missions |
| Classic, Mission List, Grid × Standard, Chaos, Randomizer Arsenal | 9/9 | 9/9 | 9/9 |
| Generated seed persisted correctly | Pass | Pass | Pass |
| Normal Shop and Classic Shop start; saved run reload | Pass | Pass | Pass |
| Fortress map and spawn preparation | Pass | Pass | Pass |
| Native Classic, Mission List, Grid, Shop, Classic Shop, Fortress starts | Pass | Pass | Pass |
| Native progression Skirmish start from a generated Grid | Pass | Pass | Pass |
| Native Challenge start | Battle City, with automatic AI teammate | Not applicable | Not applicable |
| Real GUI modes, small through large windows | Pass | Pass | Pass |
| Doubled-font GUI review | 54 views, no clipped controls | 54 views, no clipped controls | 54 views, no clipped controls |
| Existing player settings exported/reopened as Archipelago YAML | Preserved | Preserved | Preserved |
| Windows executable build, installation report, GUI startup | Pass | Pass | Pass |
| Python compilation and whitespace checks | Pass | Pass | Pass |

The seed matrix used the real mission catalogues and generation callbacks. DTA's existing player exclusions reduced that matrix's pool to ten missions; additional native starts used fresh default settings. Shop checks covered real saved runs and both ordinary stage limits and complete campaign ordering.

The GUI review resized actual launcher windows to 480×360, 800×560, and 3200×1800. It exercised Classic, Mission List, Grid, Shop, and Fortress workspaces, including Settings, Advanced, and Archipelago pages. Normal-font checks were followed by a named-font and widget-font enlargement review. Very short windows retain content space by hiding the summary and tab strip; the Views menu selects pages and nested settings. Overflowing controls remain accessible through both scroll axes.

Native checks launched the actual game engines through Wine. Readiness came from engine post-load logs, active processes, and available game-window captures. DTA's initial review used an MO-specific readiness field, which remained false even on playable maps; its Vinifera logs and captures confirmed loading, and the subsequent Skirmish check used DTA's own post-load markers. Some later captures were unavailable under the desktop compositor; engine diagnostics remained available. Intro-free installed Reloaded missions were selected for gameplay confirmation after earlier starts reached their intro movies.

## Fixes made during this review

- **MO mission loading:** the supplied log shows optional challenge discovery raising `Challenges require native one- or two-player registration.`, aborting the entire mission load. Discovery now skips and logs invalid optional registrations while preserving campaign loading. Launch-time validation stays strict. Startup and seed errors retain the original cause and expose diagnostics.
- **All three UIs:** added shared scrolling, compact workspace/details navigation, access to overflowing notebook pages through Views, bounded headings/status, smaller table minimum widths, adaptive Fortress panes, and resizable connection dialogs. The layout also handles very short windows with enlarged fonts.
- **DTA Arsenal:** replaced unusable all-zero defaults, added a one-time migration for that legacy empty state, restored installed technology tiers, and enabled clear empty-roster validation. Existing nonempty rosters and faction choices are retained.
- **Reloaded Shop and Skirmish:** removed assumptions that the campaign co-op variable exists in this launcher.
- **Reloaded Fortress:** skip inactive techno registry IDs without installed definitions when building private types, preserving existing definitions and registry indices. This resolved the observed `YADEPT` preparation failure.
- **MO and Reloaded Skirmish:** register the private player country before the engine allocates multiplayer houses, after artwork preparation, and use actual country registry order for AI indices. Preserve Windows text encoding and refuse to replace custom rules files.
- **MO Skirmish:** provide existing building clone definitions to the native building-power adapter. This resolved the observed `MORPYACNST` preparation failure.

## Candidates and evidence

Fresh Windows candidates are staged locally under `/tmp/randomizer-release-review/builds/`. Existing installed release executables were not replaced, and nothing was published.

| Candidate | SHA-256 |
| --- | --- |
| `mo/MentalOmegaRandomizer.exe` | `ffcd64be11757a7fb074a698f8fac9ae496f4fde5c74eaeca39876b2e4f72eeb` |
| `dta/DTARandomizer.exe` | `cf00e8b55d06e6567d18775491a2fabb4041db5de66c3b8b3744d69d924f11c9` |
| `reloaded/CnCReloadedRandomizer.exe` | `8580b41dc7c1c459c3dce1bb8b64fa0c0d401252fdcddfdcae978a2953ffa47b` |

Local evidence is under `/tmp/randomizer-release-review/`: per-product generation records, native launch records and logs, GUI geometry/captures, build logs, `packages.json`, and packaged installation reports. Historical records include failures found and corrected during the review; the successful later records document the fixes. This temporary directory is not included in the release.

Original player settings, progression files, and protected game-root runtime inputs were backed up and restored. Final byte comparisons against the native-review backup manifests found no differences. Review game processes and temporary executable aliases were removed. No unit tests or test dependencies were added or run.

## Remaining release coverage

- Full mission victories, defeat/retry sequences, complete campaign runs, and a full Fortress survival run were not played through. Native starts establish loading and initial gameplay only.
- Live multi-human co-op synchronization and a live Archipelago multiworld were not exercised. YAML export/reopen and existing packaged installation validation passed.
- GUI resizing and enlarged fonts were checked on the available Linux/Wine desktop. Physical Windows monitor/DPI combinations were not exhaustively checked.
- Reloaded's production release report has `passed: true` and `static_valid: true`, but still reports `release_ready: false`. Its pending live checks include every campaign family/active faction, no-build and trigger-critical missions, launches of all 108 missions, and complete campaigns. These checks were not marked complete or weakened by this review.
