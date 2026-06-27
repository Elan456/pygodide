# pygodide

**pygodide** is a modern replacement for pygbag that leverages pyodide for running pygame in the web.

## Install

```bash
pip install pygodide
```

## Headless Smoke Tests

Use `pygodide smoke` to build an app and launch it in a headless browser:

```bash
uv run playwright install chromium
uv run pygodide smoke /path/to/your/pygame/project
```

No manifest file is required for normal app smoke tests.

## Test Target Fixtures

Development fixtures live under `test_targets/`. Each target needs a
`testing_manifest.yaml` file with at least a manifest name. This file is only
for pygodide's own fixture suite:

```yaml
name: ball-bouncing
smoke:
  path: /
  timeout-ms: 120000
```

Run every target with:

```bash
uv run playwright install chromium
./scripts/smoke
```

Use `--build-only` for manifest discovery and build validation without opening a
browser. Use `--target NAME` to run a single manifest name.
