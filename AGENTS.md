# AGENTS.md

Guidance for AI coding agents (and humans) working in this repository.

## What this repo is

A **personal fork of [arch4edu/aur-auto-update](https://github.com/arch4edu/aur-auto-update)**
that automatically keeps **@debendraoli's own AUR packages** up to date. A
scheduled job checks each configured package's upstream version, and when a new
version appears it builds the package in a clean Arch Linux chroot and, if the
build succeeds, pushes the updated `PKGBUILD`/`.SRCINFO` to the AUR.

It is **not** the multi-maintainer upstream service — it only manages the
packages under [`config/debendraoli/`](config/debendraoli).

## How it works (data flow)

1. **`.github/workflows/check-update.yml`** (cron every 12h, or manual):
   - `nvchecker.py` reads every `config/**/*.yaml` and writes `nvchecker.toml`
     (per-package version source) and `oldver.json` (last-known versions).
   - `nvchecker` compares upstream vs `oldver` and writes `nvchecker.log`.
   - `process-update.py` reads `nvchecker.log`; for each **updated** package that
     exists on AUR and has `test: true`, it dispatches `build.yml`.
2. **`.github/workflows/build.yml`** (`workflow_dispatch`, inputs: `pkgbase`,
   `pkgver`):
   - `build` job: clones the AUR repo, runs `bin/update-pkgver` (bump `pkgver`,
     reset `pkgrel=1`, refresh checksums), builds in a clean chroot
     (`extra-x86_64-build`), regenerates `.SRCINFO`, validates it, runs `namcap`.
   - `push` job (only if a package was built): applies the diff, pushes to AUR
     (`bin/aur-push` → AUR `master`), then bumps `oldver` in the package YAML and
     commits it back to this repo's `main` (`bin/update-yaml` + `bin/git-push`).
3. **`.github/workflows/check-pull-request.yml`** (`workflow_dispatch`): runs
   `check-pr.py` to validate `nvchecker.toml` changes in a PR.

The clean-chroot build in step 2 **gates every AUR push** — a broken update
fails the build and is never published.

## Key files

| Path | Purpose |
| --- | --- |
| `config/debendraoli/<pkgbase>.yaml` | Per-package config (see below). |
| `config/__config__.toml` | nvchecker base config (`oldver.json`, keyfile). |
| `config/keyfile.toml` | `__GITHUB_TOKEN__` placeholder, filled in at CI time. |
| `nvchecker.py` | Builds `nvchecker.toml` + `oldver.json` from the YAML configs. |
| `process-update.py` | Reads `nvchecker.log`, dispatches builds, reports status. |
| `check-pr.py` | PR validation for nvchecker config. |
| `bin/*` | Shell helpers (`aur-clone`, `aur-push`, `update-pkgver`, `update-yaml`, `git-push`, `recv-gpg-keys`). |
| `.github/workflows/*.yml` | The three workflows above. |
| `.github/dependabot.yml` | Weekly `github-actions` update PRs. |

### Package config format

```yaml
nvchecker:
  source: github
  github: owner/repo
  use_latest_release: true
  prefix: v            # optional, stripped from the tag
test: true             # true => build + push to AUR on update
oldver: 1.2.3          # last version known on AUR; managed by the push job
```

- `test: true` is the normal path (build and publish). `flag: true` is a
  not-yet-implemented alternative (flag out-of-date on AUR).
- `oldver` is **managed automatically** by the push job after a successful AUR
  push. Only hand-edit it to intentionally resync (e.g. when adding a package,
  set it to the version currently on AUR).

## Conventions (do not regress these)

- **Action pinning:** pin **third-party** actions (`arch4edu/cactus/*`) to a full
  **commit SHA** with a `# version` comment; keep **official `actions/*`** on the
  **latest stable major tag** (e.g. `actions/checkout@v7`). Dependabot maintains
  both. Never reintroduce `@main`/`@master` for third-party actions.
- **Loud, resilient failures in `process-update.py`:** genuine problems (missing
  config for an updated package, a rejected GitHub dispatch) emit `::error::` and
  exit non-zero so the run turns red and notifies the maintainer; transient or
  expected states (AUR unreachable, package not on AUR, nvchecker source error)
  emit a non-fatal `::warning::`. Do not make transient network errors fatal, and
  do not silently swallow real errors.
- A package is only auto-updated if it exists on AUR under the **exact** pkgbase.
- The bot commits directly to `main`; keep local checkouts in sync
  (`git pull --rebase origin main`) before working.

## Adding a package

1. Confirm the package exists on AUR and `AutoUpdateBot` is a co-maintainer.
2. Add `config/debendraoli/<pkgbase>.yaml` (format above); set `oldver` to the
   version currently on AUR.
3. Test the nvchecker config locally:
   ```sh
   python nvchecker.py config/debendraoli/<pkgbase>.yaml
   nvchecker -c nvchecker.toml -e <pkgbase>
   ```

## Validating changes

No build system; validate what you touch:

```sh
python3 -m py_compile nvchecker.py process-update.py check-pr.py   # Python syntax
python3 -c 'import yaml,glob; [yaml.safe_load(open(f)) for f in glob.glob("config/**/*.yaml", recursive=True)]'
actionlint .github/workflows/*.yml                                 # workflow lint
```

Pre-existing `shellcheck` style warnings from `actionlint` on the inline build
scripts are not in scope — do not "fix" unrelated scripts.

## Secrets — never commit

- `SSH_KEY` — AUR SSH key (used by the `push` job).
- `GITHUB_TOKEN` — substituted into `config/keyfile.toml` at CI time.

`config/keyfile.toml` must keep the literal `__GITHUB_TOKEN__` placeholder.
`.gitignore` already excludes generated artifacts (`nvchecker.toml`, `*.json`,
`*.log`, `*.key`).
