# b-pass Kodi repository

Kodi add-on repositories for the b-pass add-ons, served by GitHub Pages at
https://b-pass.github.io/kodi-repo/.

There are two repositories:

| Repository add-on        | Path    | Contains                                              |
|--------------------------|---------|-------------------------------------------------------|
| `repository.b-pass`      | `/`     | The latest published GitHub release of each add-on    |
| `repository.b-pass.dev`  | `/dev/` | The current `main` branch of each add-on, and Myth Estuary |

Dev builds are versioned `<version>.dev<YYYYMMDD>.<HHMMSS>` (the commit time, UTC). So every
new commit on `main` is an update in Kodi, but a dev build still counts as older than the next
real release.

## Installing in Kodi

1. **Settings → System → Add-ons**: turn on **Unknown sources**.
2. **Settings → File manager → Add source**: enter `https://b-pass.github.io/kodi-repo/`.
3. **Add-ons → Install from zip file**: open that source and pick
   `repository.b-pass-<version>.zip` (or `dev/repository.b-pass.dev-<version>.zip` for dev
   builds).
4. **Add-ons → Install from repository**: pick the repository and install add-ons from it.

Kodi then checks for updates by itself. Dependencies such as `script.module.requests` and
`script.module.inputstreamhelper` come from the official Kodi repository.

## Publishing

```sh
./publish.py
```

This one command does everything:

- Downloads the latest release and the `main` branch of each add-on in `GITHUB_REPOS`.
- Builds both repositories into `_site/`.
- Force-pushes the result as a single commit on this repo's `gh-pages` branch.

You can run it any time, as often as you like:

- **Nothing changed:** if the result is the same as what's already published, nothing is
  pushed.
- **A download fails:** the run stops and nothing is pushed.
- **An add-on is skipped:** add-ons with no release (or no GitHub repo) are left out with a
  warning.

To build into `_site/` without pushing, run `./publish.py --no-push`.

### Releasing an add-on

1. Bump `version` in the add-on's `addon.xml` and commit it. **Kodi only updates when the
   version goes up.**
2. Publish a GitHub release for it. Attach the zip, or attach nothing and the tag's source is
   used.
3. Run `./publish.py`.

The version Kodi sees comes from the `addon.xml` inside the release, not from the tag. If the
two don't match, the script prints a warning.

To ship dev builds, push to the add-on's `main` and run `./publish.py`.

### Adding an add-on

Add its GitHub repo to `GITHUB_REPOS` in `publish.py`. Dev-only files (`tests/`, `tools/`,
`CLAUDE.md`, …) are dropped from the zips. That list is `EXCLUDE`.

An add-on that lives in a folder of a bigger repo goes in `GITHUB_FOLDERS` instead, as
`(repo, branch, folder)`. These are dev-only: they're built from that branch into the dev
repository and left out of the release one. The Myth Estuary skin (`skin.myth-estuary`) is
published this way, from `addons/skin.estuary` on the `myth-estuary-omega` branch of
`b-pass/xbmc`.

