# b-pass Kodi repository

Kodi add-on repositories for the b-pass add-ons, served by GitHub Pages at
https://b-pass.github.io/kodi-repo/.

There are two repositories:

| Repository add-on        | Path    | Contains                                              |
|--------------------------|---------|-------------------------------------------------------|
| `repository.b-pass`      | `/`     | The latest published GitHub release of each add-on    |
| `repository.b-pass.dev`  | `/dev/` | The current `main` branch of each add-on, and Myth Estuary betas |

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

Or download the repository zip from this repo's
[releases page](https://github.com/b-pass/kodi-repo/releases), copy it to the Kodi device, and
use **Install from zip file** on it in place of steps 2 and 3.

Kodi then checks for updates by itself, the repository add-on included: each repository lists
itself. Dependencies such as `script.module.requests` and
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

### Releasing the repository add-ons

The repository add-ons are in this repo (`repository.b-pass/`, `repository.b-pass.dev/`). Each
repository lists its own add-on, so installed copies update like any other add-on. Change one
only for something like new URLs, and bump its `version`:

1. Bump `version` in its `addon.xml`, commit and push, then run `./publish.py`.
2. Attach the new zip from `_site/` to a GitHub release, so people can download it. The dev
   one is kept off "Latest", so the releases page points people at the regular one:

   ```sh
   gh release create repository.b-pass-v<version> _site/repository.b-pass-<version>.zip --latest
   gh release create repository.b-pass.dev-v<version> _site/dev/repository.b-pass.dev-<version>.zip --latest=false
   ```

### Adding an add-on

Add its GitHub repo to `GITHUB_REPOS` in `publish.py`. Dev-only files (`tests/`, `tools/`,
`CLAUDE.md`, …) are dropped from the zips. That list is `EXCLUDE`.

An add-on released from a repo that holds other things too goes in `GITHUB_TAGGED` instead,
as `(repo, tag prefix)`. Only its GitHub releases with that tag prefix are used, never a
branch: pre-releases go to the dev repository, and full releases to both.

The Myth Estuary skin (`skin.myth-estuary`) is published this way, from `b-pass/xbmc` with
tags `skin.myth-estuary-v<version>`. Its releases are made by
`tools/myth-estuary-release.sh` on that repo's `myth-estuary-omega` branch, which packs the
textures and zips the skin: `--beta` makes a pre-release and `--release` a full one. Then run
`./publish.py`.
