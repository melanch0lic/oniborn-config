# oniborn-config

The update configuration of ONIBORN, published with GitHub Pages. The game reads
`versions.json` to tell players that a new version exists and, in exceptional cases, to
require one. It decides **policy only**: what was released and which builds are still
supported. The stores decide what each player can actually install, and the game never
downloads or runs anything from here.

Everything in this repository is public. Never put a secret, a key or a private address in it.

```text
oniborn-config/
├── README.md                     this guide
├── versions.json                 the configuration the game reads
├── versions.schema.json          its JSON Schema (shape and bounds)
├── scripts/validate.py           the rules the game applies, and more strictly
├── changelogs/en.json, ru.json   release history (not read by the game)
├── examples/                     ready-made configurations for common cases
├── .github/workflows/validate-config.yml
└── .nojekyll                     serve files as they are (no Jekyll)
```

## How the game uses it

- It fetches `versions.json` in the background at launch, again when it returns to the
  foreground once `checkIntervalHours` have passed, after the player comes back from the store,
  and when the player taps **Check for updates** in Settings. A request is bounded by
  `requestTimeoutSeconds`; one never delays the game. Offline, it plays on as always.
- It keeps the last valid copy on the device for `maxCacheAgeHours`. A kept copy can inform the
  player, but **only a copy fetched from the network in this check can require an update**.
- Any invalid configuration (bad JSON, a missing or mistyped field, a version that is not
  `major.minor.patch`, `minSupportedBuild` above `latestBuild`, a store link that is not this
  game's official page, a timing out of bounds, an unknown `schemaVersion`) is ignored as a
  whole: the game behaves as if there were no configuration. It can never require an update.
- **Optional update**: the installed build is below `latestBuild` and the store offers an
  update to this installation. A dialog shows once (at the main menu, never during a run); after
  **Later** a small sign stays in the menu, and the dialog returns after
  `reminderIntervalHours` or as soon as a newer build is announced. On Android it downloads in
  the background with Google Play's flexible update and asks for a restart at the menu.
- **Required update**: only when *all* hold: `forceUpdateEnabled` is `true`, the installed build
  is below `minSupportedBuild`, the configuration was just fetched, and the store confirms an
  update that reaches `minSupportedBuild` (Android: Google Play offers it and allows an
  immediate update; iOS: Apple's public lookup lists the announced version in the player's
  storefront, for their iOS version). The player cannot start or continue a run until they
  update; a run under way is never interrupted. If the store fails to deliver twice in a
  session, or the player is offline when they tap **Check again**, the requirement is lifted
  for the session: nobody is locked out by a store problem.
- **Unavailable**: announced, but the store does not offer it to this player yet (staged
  rollout, region, device). Nothing is shown.
- The game never suggests a downgrade: a build at or above `latestBuild` (an internal test
  build, for example) is up to date.

Fields:

| Field | Meaning |
|---|---|
| `schemaVersion` | Always `1` for this file. Fields may be added without changing it (older games ignore fields they do not know). |
| `updateCheckEnabled` | The global kill switch. `false`: no notification, no requirement, anywhere. |
| `android`, `ios` | One block per store, managed independently. A missing block means disabled for that store. |
| `enabled` | This store's players hear of updates at all. |
| `latestVersion` | The version name of the newest released build, `major.minor.patch` (pubspec's `version:` before `+`). |
| `latestBuild` | Its build number (Android `versionCode`, iOS `CFBundleVersion`: pubspec's number after `+`). |
| `minSupportedBuild` | Builds below it are unsupported. Only enforced together with `forceUpdateEnabled`. |
| `forceUpdateEnabled` | Explicit switch for required updates. Keep `false` unless there is a critical reason. |
| `storeUrl` | Android: `https://play.google.com/store/apps/details?id=com.oniborn.app`. iOS: `https://apps.apple.com/app/id<APP_STORE_ID>`. `null` only while the store is disabled. |
| `releaseNotes` | What `latestVersion` brings, by language tag: `en`, `ru`, `pt_BR`, `zh_Hant`... at most 12 notes of 300 characters. The game shows the player's exact language, else the base language, else `en` (required when there are notes), else none. Notes are shown only when the store offers exactly `latestBuild`. |
| `settings` | `reminderIntervalHours` 1–720 (24), `checkIntervalHours` 1–168 (6), `requestTimeoutSeconds` 1–30 (5), `maxCacheAgeHours` 1–720 (24). Each may be omitted. |

`changelogs/<language>.json` keep the history of release notes, newest first. The game does
not fetch them; the current notes are inline in `versions.json` to save a request.

## 1. Create the repository

1. On GitHub: **New repository**, name `oniborn-config`, **Public** (GitHub Pages on a free
   account needs a public repository), no template.
2. Copy the contents of this folder (`tool/oniborn-config/` in the game's repository) into it,
   hidden files included (`.github/`, `.nojekyll`):

   ```sh
   git clone https://github.com/<github-username>/oniborn-config.git
   cp -R <game>/tool/oniborn-config/. oniborn-config/
   cd oniborn-config
   python3 scripts/validate.py versions.json examples/*.json --changelogs changelogs
   git add -A && git commit -m "chore: initial update configuration" && git push
   ```

3. Check that **Actions** shows a green `validate-config` run.

## 2. Enable GitHub Pages

**Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main`,
folder `/ (root)` → Save.** The first deployment takes a minute or two (Actions shows a
`pages-build-deployment` run).

## 3. Publish the initial configuration

`versions.json` as committed is the initial production configuration: Android 1.4.1 (8), forced
updates off, iOS disabled. Before pushing, confirm that build 8 is actually live on Google Play;
if the live build is another, set `latestVersion`/`latestBuild` to it.

## 4. The configuration URL

```text
https://<github-username>.github.io/oniborn-config/versions.json
```

Open it in a browser: it must show the JSON (not a 404 page). `curl -I` on it shows
`content-type: application/json` and an `etag`.

## 5. Connect it to ONIBORN

In the game's `.env` (copied from `.env.example`, never committed):

```sh
ONIBORN_UPDATE_CONFIG_URL=https://<github-username>.github.io/oniborn-config/versions.json
```

Then build as usual (`flutter build appbundle --release`). Empty or missing, the game never
checks for updates and shows only its version in Settings. Only an `https` address is accepted.
The address is compiled into each build: choose it once; moving it later needs a new release (keep
the old one serving a valid file until no player uses those builds).

## 6. Announce a new Android release

Only once the build is **live** on Google Play for its audience (review passed, rollout started,
the listing installs it):

```json
"android": {
  "enabled": true,
  "latestVersion": "1.5.0",
  "latestBuild": 9,
  "minSupportedBuild": 1,
  "forceUpdateEnabled": false,
  "storeUrl": "https://play.google.com/store/apps/details?id=com.oniborn.app",
  "releaseNotes": { "en": ["..."], "ru": ["..."] }
}
```

During a staged rollout, announcing is safe: Google Play tells each installation whether it can
have the update, and players outside the rollout see nothing. See `examples/optional-update.json`.

## 7. Announce a new iOS release

When the game is first live on the App Store, take its id from the App Store page address
(`https://apps.apple.com/app/oniborn/id1234567890` → `id1234567890`) and set:

```json
"ios": {
  "enabled": true,
  "latestVersion": "1.5.0",
  "latestBuild": 9,
  "minSupportedBuild": 1,
  "forceUpdateEnabled": false,
  "storeUrl": "https://apps.apple.com/app/id<APP_STORE_ID>",
  "releaseNotes": { "en": ["..."], "ru": ["..."] }
}
```

iOS has no in-app update API: the game opens the App Store page. Apple's public lookup is used as
a sign that the version is listed in the player's storefront, never as proof that this device can
install it. See `examples/ios-release.json` (its id is a placeholder: replace it). Keep
`forceUpdateEnabled` `false` on iOS.

## 8. Release notes

Under `releaseNotes`, one list per language; `en` is required whenever there are notes. Use the
game's language tags (`en`, `ru`, `es`, `pt_BR`, `de`, `fr`, `ja`, `ko`, `zh`, `zh_Hant`, `hi`, `tr`,
`it`, `id`, `vi`, `pl`, `uk`, `ar`, `nl`, `th`, `cs`, `ro`, `sv`, `ms`, `bn`). Keep each note short:
the dialog is compact and scrolls past four or five. Add the same notes to
`changelogs/<language>.json` (newest first) to keep the history.

## 9. Optional updates

The default. Raise `latestVersion` and `latestBuild`; leave `forceUpdateEnabled` `false`. Players
on older builds get the dialog once, then the sign in the menu; **Later** waits
`reminderIntervalHours`.

## 10. Requiring an update (exceptional)

Only for a critical problem (a crash on launch, save corruption, a broken server contract):

1. Publish the fixed build and wait until it is **live for the whole intended audience**: the
   staged rollout at 100%, every country, every supported device. On iOS, wait until the App Store
   lists the version in every storefront.
2. Install it from the store on a real device to confirm it is offered.
3. Set `minSupportedBuild` to the first build that is safe, and `forceUpdateEnabled` to `true`
   (see `examples/required-update.json`). The validator prints a warning as a reminder.
4. Watch reviews, support mail and Google Play's vitals for a day. If players cannot update,
   **set `forceUpdateEnabled` to `false` at once** (section 12).

The game also protects players by itself: it enforces only what the store confirms, lifts the
requirement after two failed attempts in a session, and never enforces from a kept copy.

Never enable forced updates just because a new version exists.

## 11. Disable the whole update system

Set `"updateCheckEnabled": false` (see `examples/kill-switch.json`) and push. Every notification,
sign and requirement disappears at the next check of each game (launch, return from background
after the interval, or Settings → Check for updates), once the CDN copy expires (section 14).

## 12. Roll back an incorrect configuration

```sh
git revert HEAD        # or edit the values back
git push
```

Pages redeploys in about a minute; games pick it up at their next check. A game that already
read a wrong but *valid* configuration keeps showing it until its next check; it can never be
locked out by it: required updates need a fresh fetch and the store's confirmation.

## 13. Validate before deploying

Locally:

```sh
python3 scripts/validate.py versions.json examples/*.json --changelogs changelogs
pip install "check-jsonschema==0.29.4"
check-jsonschema --schemafile versions.schema.json versions.json examples/*.json
```

The `validate-config` workflow runs both on every push and pull request.

**Protecting main** (recommended): change the configuration through pull requests, and in
**Settings → Branches → Add rule** for `main`, require the `validate` status check. Pages then
never publishes a configuration that failed validation. Without the rule, a direct push is
published even if the check fails; the game still ignores an invalid file, but fix it at once.

## 14. CDN caching and propagation

- GitHub Pages serves through a CDN with `Cache-Control: max-age=600`: a change can take up to
  about 10 minutes to reach every player, plus the deployment itself (about a minute).
- The game sends `If-None-Match` with the last ETag; an unchanged file costs a `304` and no body.
  It never adds cache-busting query strings.
- To see what players get: `curl -sI https://<github-username>.github.io/oniborn-config/versions.json`
  (look at `etag`, `last-modified`, `age`) and `curl -s ... | python3 -m json.tool`.
- A 404 right after enabling Pages: wait for the first `pages-build-deployment` to finish, and
  check that the file is at the root of `main`.
- On a phone, Settings → **Check for updates** asks at once (at most once per 10 seconds).
  Coming back to the foreground asks only after `checkIntervalHours`.

## Changing the schema

Adding an optional field never needs a new `schemaVersion`: released games ignore it. A change
that older games would misread (renaming or retyping a field) must not be made to
`versions.json`: publish it as a new file (for example `versions-v2.json`) read by new builds,
and keep `versions.json` valid for the builds still in use.
