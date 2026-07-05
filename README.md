# pygodide

**BETA — everything is subject to change**

Pronounced "pie-go-died", **pygodide** turns Pygame projects into browser apps
using [Pyodide](https://pyodide.org/). It bundles your code and assets, installs
Python dependencies in the browser, and generates the HTML and JavaScript needed
to run your game on the web.

**Documentation**: [https://elan456.github.io/pygodide/](https://elan456.github.io/pygodide/)

Already have a Pygame project? You can put it in the browser and share a link —
or upload to [itch.io](https://itch.io) as an HTML game with `pygodide build . --zip`.
No rewrite required for most small games. See the
[instructions](https://elan456.github.io/pygodide/instructions/#publishing-to-itchio)
for details.

## Install

```bash
pip install pygodide
```

## Quick start

From your project root:

```bash
pygodide build .
pygodide serve .
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

By default, pygodide looks for `main()` in `main.py`, reads dependencies from
`requirements.txt` or `pyproject.toml`, and auto-converts simple synchronous game
loops for the browser.

You can also build and serve in one step:

```bash
pygodide build . --serve
```

Use a different port with `pygodide serve . --port 3000`.

## Full guide

The [instructions](https://elan456.github.io/pygodide/instructions/) cover
troubleshooting, custom entry points, dependencies, manual async conversion, and
smoke testing.

## Common commands

| Command | What it does |
| --- | --- |
| `pygodide build .` | Bundle your project into `build/` |
| `pygodide serve .` | Serve the built app locally (default port `8000`) |
| `pygodide smoke .` | Build and test in a headless browser |
| `pygodide smoke . --verbose` | Show full build and smoke output on the console |
| `pygodide build . --app game:start` | Use a different entry function |
| `pygodide build . --dep numpy` | Add an extra dependency for this build |
| `pygodide build . --no-auto-async` | Disable automatic game-loop conversion |

Build output is logged to `build/pygodide-build.log`. Smoke tests also write
`build/pygodide-smoke.log`.

## Examples

Sample projects live under
[`test_targets/`](https://github.com/Elan456/pygodide/tree/main/test_targets):

- [ball bouncing](https://github.com/Elan456/pygodide/tree/main/test_targets/ball_bouncing) — minimal async Pygame game
- [not async](https://github.com/Elan456/pygodide/tree/main/test_targets/not_async) — sync loop converted automatically at build time
- [numpy particles](https://github.com/Elan456/pygodide/tree/main/test_targets/numpy_particles) — larger game with extra dependencies

Try one locally:

```bash
pygodide build test_targets/ball_bouncing
pygodide serve test_targets/ball_bouncing
```

## Developing

```bash
git clone https://github.com/Elan456/pygodide.git
cd pygodide
uv sync --dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Run the same checks as CI:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

### Smoke tests

`pygodide smoke` builds an app and launches it in headless Chromium. End-user
projects do not need any extra manifest file.

```bash
uv run playwright install chromium
uv run pygodide smoke /path/to/your/pygame/project
```

The repository also maintains fixtures under `test_targets/`, each with a
`testing_manifest.yaml`. Run the full fixture suite with:

`uv run pygodide smoke test_targets --suite`