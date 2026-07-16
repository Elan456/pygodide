# Test targets

Fixture Pygame apps used by the smoke suite and as small demos. Each
subdirectory is a complete project. End-user games do **not** need a
`testing_manifest.yaml`; that file is only for this suite.

## Run the suite

From the repository root (needs the smoke extra + Chromium; see the main
README):

```bash
uv run pygodide smoke test_targets --suite
uv run pygodide smoke test_targets --suite --target ball-bouncing
uv run pygodide smoke test_targets --suite --build-only   # no browser
```

`--target` filters by the manifest `name` field (not the directory name).
Repeat `--target` for multiple fixtures.

## Manifest schema (`testing_manifest.yaml`)

Required for every target directory under `test_targets/`. Unknown top-level
or nested keys are rejected.

```yaml
# Required. Unique across the suite. Used by --target.
name: my-fixture

# Optional. Human-readable summary (shown in docs/tables).
description: What this fixture exercises.

# Optional. Overrides applied when the suite builds this target.
build:
  app: main:main          # module:callable entrypoint
  deps:                   # extra pip requirements for this build only
    - some-package
  auto-async: true        # force auto-async on/off for this target

# Optional. Browser smoke settings (defaults shown).
smoke:
  path: /                 # URL path; must start with /
  ready-log: "[pygodide] ready"
  timeout-ms: 120000      # wait for ready log + loading UI to clear
  post-ready-ms: 500      # keep listening for errors after ready
  # Hang / expected-failure fixtures (optional):
  # expected-warning: "[pygodide] async hang"  # substring in console or #status
  # expect-ready: false                        # default false when expected-warning set
```

| Field | Required | Notes |
| --- | --- | --- |
| `name` | yes | Unique suite id; CLI `--target` matches this |
| `description` | no | Documentation only |
| `build.app` | no | Same `module:callable` form as CLI `--app` |
| `build.deps` | no | List of requirement strings |
| `build.auto-async` | no | Boolean; overrides project/default auto-async |
| `smoke.path` | no | Must start with `/` |
| `smoke.ready-log` | no | Console message that marks success |
| `smoke.timeout-ms` | no | Positive integer (milliseconds) |
| `smoke.post-ready-ms` | no | Non-negative integer (milliseconds). For hang fixtures (`expect-ready: false`), used as a short confirm window that ready does not appear after the expected warning. |
| `smoke.expected-warning` | no | Substring that must appear in a console message or `#status` text. Used for positive hang/stuck fixtures. |
| `smoke.expect-ready` | no | Boolean. Defaults to `true`, or `false` when `expected-warning` is set. When `false`, ready is not required and becoming ready is a failure. |

Project config (`pyproject.toml` / `requirements.txt` / `[tool.pygodide]`) still
applies as usual. Manifest `build` fields are suite-level overrides for that
fixture only.

## Add a new target

1. Create `test_targets/<directory>/` with a playable app (`main.py` by default,
   or set `[tool.pygodide].app` / `build.app`).
2. Add dependencies via `requirements.txt` and/or `pyproject.toml` like a real
   project.
3. Add `testing_manifest.yaml` with a **unique** `name` and a short
   `description`. Set `smoke.timeout-ms` high enough for the first ready log.
4. Smoke it alone, then as part of the suite:

   ```bash
   uv run pygodide smoke test_targets/<directory> --verbose
   uv run pygodide smoke test_targets --suite --target <manifest-name>
   ```

5. Prefer a small fixture that fails if its feature regresses. Do not commit
   `build/` output (`build/` is gitignored).

Discovery rule: every **immediate subdirectory** of `test_targets/` that is a
directory must contain a valid `testing_manifest.yaml`. Non-fixture dirs will
break `--suite`.
