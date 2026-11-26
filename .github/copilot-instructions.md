# GitHub Copilot instructions

This repo is a personal fork of `arch4edu/aur-auto-update` that auto-updates
**@debendraoli's own AUR packages** (configured under `config/debendraoli/`).

**Read [`AGENTS.md`](../AGENTS.md) for the full architecture, data flow, file
map, and workflows.** Key rules to follow here:

- **Action pinning:** pin **third-party** actions (`arch4edu/cactus/*`) to a
  commit SHA with a `# version` comment; keep **official `actions/*`** on the
  latest stable major tag (e.g. `actions/checkout@v7`). Dependabot maintains
  both. Never use `@main`/`@master` for third-party actions.
- **`process-update.py` failure policy:** genuine errors (missing config for an
  updated package, rejected GitHub dispatch) → `::error::` + non-zero exit (red
  run); transient/expected states (AUR unreachable, package not on AUR, nvchecker
  source error) → non-fatal `::warning::`. Don't make transient network errors
  fatal; don't silence real errors.
- A package is auto-updated only if it exists on AUR under the exact pkgbase.
  `oldver` in each package YAML is managed by the push job — hand-edit only to
  resync.
- Never commit secrets; keep the `__GITHUB_TOKEN__` placeholder in
  `config/keyfile.toml`.

Validate changes you make:

```sh
python3 -m py_compile nvchecker.py process-update.py check-pr.py
actionlint .github/workflows/*.yml
```
