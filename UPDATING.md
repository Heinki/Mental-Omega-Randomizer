# Launcher updates through GitHub Releases

The packaged Windows launcher checks this project's public GitHub repository
after startup. Checks run in the background. Offline access, rate limits, or an
incomplete release do not prevent playing. Source launches do not check for or
install executable updates.

When a newer stable release is available, the launcher shows one automatic
update prompt per version. Choosing **No** or closing the prompt remembers that
version across launcher restarts. An **Update** button remains in the upper
right corner, including when Details are hidden. A different newer release can
prompt again. Notice history is stored in the launcher's data directory under
`updates/state.json`, separately from run saves and player settings.

Accepting downloads the launcher and matching APWorld from the same release,
checks their sizes and SHA-256 checksums, closes the launcher, replaces both
files in the game folder, and restarts it. The helper is a temporary copy of the
existing launcher; no Python installation, account, service, or extra installer
is required. The installation directory must be writable. Keep the original
launcher filename.

Updates are postponed while a mission, multiplayer connection, or launcher
operation is active. No game process is terminated. Run saves, settings, maps,
game files, and progression are not replaced. Save-format compatibility still
depends on the new release; finishing a run before updating remains an option.

The matching APWorld is placed beside the launcher. Players must install it in
their separate Archipelago installation before generating a new multiworld.
Do not mix launcher/APWorld releases within an existing multiworld.

## Publishing with GitHub Actions

Update `APP_VERSION` in `randomizer/core/version.py` and the setup guide before
creating the release tag. Commit and push these changes first: Actions builds
the tagged commit, so an uncommitted version bump cannot fix a tagged build.

From the project root, check the intended tag before creating and pushing it:

```sh
python tools/write_release_manifest.py --verify-tag-only --tag V1.45
```

Use the tag that matches the intended `APP_VERSION`. CI checks this match before
installing build dependencies, then verifies the complete built bundle before
uploading assets and preparing a draft release.

If a tag already points to a commit with the wrong version, rerunning that job
still builds the same incorrect source. A failed, unpublished tag must point to
the corrected commit, or use a new version and matching tag. Do not move a tag
for an already published release.

## Publishing manually

1. Increment `APP_VERSION` in `randomizer/core/version.py`. Use a dotted numeric
   version and a matching GitHub tag, such as `v1.45` for `1.45`.
2. Build with `build_archipelago_release.ps1`, or `build_all_linux.sh` when using
   Wine. Both workflows prepare `release_manifest.json` and `SHA256SUMS.txt`
   alongside the launcher and APWorld. For other manual builds, run:

   ```sh
   python tools/write_release_manifest.py --launcher /path/to/MentalOmegaRandomizer.exe --apworld /path/to/mental_omega.apworld --output-directory release
   ```

3. Create a draft GitHub release and attach the launcher, matching APWorld,
   `release_manifest.json`, `SHA256SUMS.txt`, and the generated Archipelago setup
   guide. The tag-triggered GitHub build
   also prepares a draft with these assets; it does not publish it automatically.
   If that tag already has a published release, CI skips release uploads and
   keeps the verified bundle in the workflow run's artifacts. Existing drafts
   receive the new build assets. Release lookup and upload errors still fail CI.
4. Publish when ready and mark the release as latest. Drafts and prereleases
   never trigger stable update prompts. Normal commits do not trigger prompts.

The updater requires the manifest's launcher version to match the tag and
requires both product assets. CI validates the complete release bundle, including all checksums and the
APWorld archive version. Version-tag builds also require the tag to match
`APP_VERSION` before uploading. Uploading only an EXE is insufficient. Upload all
assets before publishing. Build a new version rather than changing the assets
of an already published release.

Players on versions without the updater must download an updater-enabled
launcher manually once. They can then accept future releases inside the launcher.

## Recovery and verification

Downloads and helper files live in a unique directory under `updates/update-*`
inside the launcher's data directory. Previous launcher/APWorld files remain in
that directory's `backup` subfolder. Replacement or restart-launch failures
restore previous files when possible; any failed restoration displays the
backup location for manual recovery. This is not a health check of the new
launcher's startup or gameplay. After a successful update, old update directories
can be removed once the player no longer needs their backups.

The updater uses HTTPS and the release's published SHA-256 values. These detect
damaged or mismatched downloads; they are not independent publisher signatures.

Before shipping the first updater-enabled release, manually verify on Windows:
the first newer-version prompt; declining and restarting without another prompt;
the retained Update button; a different newer version prompting again; an
accepted update restarting in the same folder; preserved run data; offline
startup; blocked updates during gameplay; and recovery from a locked target.
