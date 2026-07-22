# Instructions

This guide gets a typical Pygame project running in the browser. Start with the
quick path below; if something breaks, use the troubleshooting links to jump to the
relevant section.

## Quick start

From your project root:

```bash
pygodide build .
pygodide serve .
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

That is enough for many projects. By default, pygodide:

- looks for a `main()` function in `main.py`
- reads dependencies from `requirements.txt` and/or `pyproject.toml`
- auto-converts simple synchronous game loops for the browser

Use a different port with `pygodide serve . --port 3000`, or build and serve
in one step:

```bash
pygodide build . --serve --port 3000
```

Build details are written to `build/pygodide-build.log`.

## Something went wrong?

| Symptom | What to try |
| --- | --- |
| Build fails or packages are missing | [Declare dependencies](#dependencies) |
| The wrong function runs, or nothing starts | [Set the entry point](#entry-point) |
| The page stays on "Loading..." or the game freezes | [Make the game async-compatible](#make-the-game-async-compatible) |
| `ModuleNotFoundError` in the browser | [Python path](#python-path) |
| Asset `FileNotFoundError` in the browser | [Assets and paths](#assets-and-paths) |
| You are not sure what failed | [Run a smoke test](#check-your-build-with-a-smoke-test) |

## Check your build with a smoke test

`pygodide smoke` builds your app and opens it in a headless browser. Use it to
catch load/startup failures before you debug in a real browser.

### Install for smoke tests (pip)

You need two things: the `smoke` extra (Playwright Python package) and a
Chromium browser binary for Playwright.

```bash
# 1. Install pygodide with Playwright support
pip install 'pygodide[smoke]'

# 2. Download the Chromium binary Playwright uses (once per machine/env)
playwright install chromium
```

### Run a smoke test

From your game project root:

```bash
pygodide smoke .
```

Recommended when something looks wrong:

```bash
pygodide smoke . --verbose
```

By default the console only shows pass/fail. The full log is always written to
`build/pygodide-smoke.log` (dependency resolution, auto-async status, browser
errors).

Build only, without launching a browser (no Chromium needed):

```bash
pygodide smoke . --build-only --verbose
```

### Smoke suite (multiple fixtures)

With `--suite`, PATH is a directory of fixture apps each with a
`testing_manifest.yaml` (see the repo `test_targets/` folder). Per-target
overrides come from those manifests. Single-app flags such as `--app`,
`--dep`, canvas options, `--smoke-path`, `--timeout-ms`, `--post-ready-ms`,
and `--ready-log` cannot be combined with `--suite` (pygodide errors instead
of ignoring them).

## Make the game async-compatible

Pygame games need to yield to the browser event loop. Pygodide tries to do this
automatically during `pygodide build` by inserting `await asyncio.sleep(1/120)` into
simple `while` game loops in your entrypoint (or a helper it calls directly).

If the game never yields, hang guidance is painted before the entrypoint runs
so you can still read fix steps on a frozen page.

Check whether auto-async worked:

```bash
pygodide smoke . --verbose
```

Look for `Auto async: transformed ...` in the output or log. If you see
`Auto async: skipped ...`, convert the game manually using the steps below.

Disable auto-conversion with `pygodide build . --no-auto-async` or in
`pyproject.toml`:

```toml
[tool.pygodide]
auto-async = false
```

### Manual conversion

1. `import asyncio`
2. Change `def main():` to `async def main():`
3. Add `await asyncio.sleep(1 / (fps * 2))` once per frame inside the main loop
   (half a frame budget so work + yield can still hit your target FPS)
4. Keep local runs working with:

```python
if __name__ == "__main__":
    asyncio.run(main())
```

Pygodide imports your configured entry function in the browser, so the
`if __name__ == "__main__":` block is only for local runs.

### Minimal example

```python
import asyncio
import pygame

SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

async def main():
    clock = pygame.time.Clock()
    fps = 60
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((0, 0, 0))
        pygame.display.update()
        clock.tick(fps)
        # Half a frame budget: yields for paint without always undershooting FPS.
        await asyncio.sleep(1 / (fps * 2))

if __name__ == "__main__":
    asyncio.run(main())
```

Larger examples:

- [ball bouncing](https://github.com/Elan456/pygodide/blob/main/test_targets/ball_bouncing/main.py): already-async game
- [not async](https://github.com/Elan456/pygodide/blob/main/test_targets/not_async/main.py): sync loop that auto-asyncifies at build time
- [numpy particles](https://github.com/Elan456/pygodide/blob/main/test_targets/numpy_particles/main.py): custom entry point and extra dependencies

## Configure your project

### Entry point

If your game does not start at `main()` in `main.py`, tell pygodide which
function to run. The value uses `module:callable` format: a Python import path,
not a filename:

```toml
[tool.pygodide]
app = "main:web_main"
```

Or for a one-off build:

```bash
pygodide build . --app main:web_main
```

CLI `--app` overrides `[tool.pygodide].app`.

### Dependencies

Pygodide installs your Python packages in the browser. It merges dependencies
from these sources, in order (later entries override earlier ones for the same
package name):

1. `requirements.txt`
2. `[project].dependencies` in `pyproject.toml`
3. `[tool.pygodide].dependencies`
4. groups listed in `[tool.pygodide].dependency-groups`
5. repeated `--dep` flags on the CLI

Declare each package once when you can. The build log and `pygodide smoke .
--verbose` show what was found and how each package will be installed:

- `pygame-ce` → `pyodide.loadPackage(...)`
- everything else → `micropip.install(...)`

**Without `pyproject.toml`:** add a `requirements.txt` (see the
[ball bouncing](https://github.com/Elan456/pygodide/tree/main/test_targets/ball_bouncing)
example) and/or pass `--dep` on the command line.

### Assets and paths

Load assets with paths relative to the project root, as you would locally:

```python
pygame.image.load("assets/sprites/player.png")
pygame.mixer.Sound("sounds/jump.ogg")
```

The working directory is the project root, so those paths usually work as-is.
A browser `FileNotFoundError` means a wrong path or a file that was not copied
into the build. `python-path` does not affect asset loading; see
[Python path](#python-path) for imports only.

See [asset maze](https://github.com/Elan456/pygodide/tree/main/test_targets/asset_maze)
for nested assets loaded by plain relative paths.

#### What gets copied into the build

`pygodide build` copies project files into `build/`. Only those files are
available in the browser (and in an itch ZIP).

- Without `include`: auto-discovery copies most files. It skips tooling such as
  `.git`, `.venv`, `build`, `__pycache__`, `pyproject.toml`, and prior itch
  outputs named `<project-folder>.zip` or `build.zip`.
- With `include`: only matching paths are copied (an allowlist). Use this to
  leave out docs, tools, or other extras. The entry module must match or the
  build fails.

```toml
[tool.pygodide]
include = ["main.py", "game/**", "sprites/**", "sounds/**"]
```

#### Include patterns

`include` uses
[pathlib globs](https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob)
relative to the project root (not regex, not basename-only matching).

| Pattern | Meaning |
| --- | --- |
| `main.py` | Exact file at the project root |
| `assets/*` | Files directly under `assets/` (one level) |
| `assets/**` | All files under `assets/` (any depth) |
| `**/*.png` | All `.png` files in the project |
| `**` | All files under the project root |

Patterns are rooted at the project (`sprites/**`, not `/sprites/**`). `*` is
one path segment; `**` is any depth. Each pattern must match at least one
file. Tooling dirs and prior itch ZIPs are still skipped.

#### Saves and favicon

`open()` / `pathlib` work for the current page session (see
[save slots](https://github.com/Elan456/pygodide/tree/main/test_targets/save_slots)).
A reload clears that virtual disk; durable saves are not provided yet.

A root favicon (`favicon.svg`, `.png`, `.ico`, and a few other names) is used
for the tab icon when present; otherwise pygodide ships a default.

### Python path

Default `python-path = ["."]` is enough for most projects. It adds folders to
`sys.path` before importing your entry function. It does not control asset
file paths.

You usually do not need extra entries for asset folders, normal packages
(`import game`), or installed dependencies.

Add entries when you import loose modules from non-package folders:

```text
my-game/
  main.py
  src/
    gameplay.py
  lib/
    helpers.py
```

```python
# main.py
from gameplay import run
from helpers import load_level
```

If that needs `PYTHONPATH=src:lib` locally, mirror it:

```toml
[tool.pygodide]
python-path = [".", "src", "lib"]
```

Entries are relative to the project root; keep `"."` first when you use it.
Prefer real packages (`from lib.helpers import ...`) over growing
`python-path`. For a `src/` layout where imports assume that root, add
`"src"`.

### Canvas size

These options set the HTML canvas size. They do not change Pygame's
`set_mode(...)` resolution; the surface is scaled to the canvas.

By default, pygodide scans packaged Python for `set_mode((width, height))`
(including simple constants like `SCREEN_WIDTH`), preferring the entry module.
Dummy surfaces such as `set_mode((1, 1), pygame.NOFRAME)` are ignored. Fallback:
800x600.

| Setting | What you see |
| --- | --- |
| Default | Fixed canvas at discovered `set_mode` size |
| `--canvas-width` / `--canvas-height` | Fixed pixel box |
| `--canvas-fit` | Largest size in the viewport that keeps aspect |
| `--canvas-width N --canvas-height M --canvas-fit` | Fit using N×M as the aspect |
| `--canvas-fill` | Fill the viewport (aspect may change) |

`canvas-fit` and `canvas-fill` cannot be combined.

### Detecting the web runtime

For “am I in the browser WASM build?”:

```python
import sys

if sys.platform == "emscripten":
    # browser / web build
    ...
```

True under pygodide; false under normal desktop CPython. Use a second check
only for Pyodide-specific APIs (`js`, `pyodide.ffi`, …):

```python
if "pyodide" in sys.modules:
    ...
```

See
[web_runtime](https://github.com/Elan456/pygodide/tree/main/test_targets/web_runtime)
for a smoke-tested example.

### `pyproject.toml` reference

```toml
[project]
name = "my-game"
version = "0.1.0"
dependencies = [
    "pygame-ce",
    "numpy>=1.26",
]

[dependency-groups]
web = ["fastquadtree"]

[tool.pygodide]
app = "main:web_main"
auto-async = true
include = ["main.py", "sprites/**", "sounds/**"]
title = "My Game"
# canvas-fit = true
# canvas-width = 960
# canvas-height = 540
# canvas-fill = true
# python-path = [".", "src", "lib"]
dependencies = ["pyyaml"]
dependency-groups = ["web"]
```

| Field | Purpose |
| --- | --- |
| `app` | Entry `module:callable`. Default `main:main`. [Entry point](#entry-point). |
| `auto-async` | Auto game-loop conversion. Default `true`. |
| `include` | Allowlist of files to copy (path globs). [Assets and paths](#assets-and-paths). |
| `title` | HTML page title. Default: project directory name. |
| `canvas-width`, `canvas-height` | Fixed size, or aspect with `canvas-fit`. [Canvas size](#canvas-size). |
| `canvas-fit` | Scale to viewport, keep aspect. |
| `canvas-fill` | Stretch to fill viewport (aspect may change). |
| `python-path` | Extra `sys.path` roots. Default `["."]`. [Python path](#python-path). |
| `dependencies` | Extra browser packages. [Dependencies](#dependencies). |
| `dependency-groups` | Named groups from the pyproject to install. |

[numpy particles](https://github.com/Elan456/pygodide/tree/main/test_targets/numpy_particles)
shows `[project].dependencies` plus `app = "main:web_main"`.

## Publishing to itch.io

Once your build works locally, you can package it for
[itch.io](https://itch.io) HTML uploads:

```bash
pygodide build . --zip
```

This builds your project and writes `<project-name>.zip` in the project
directory, with `index.html` at the archive root. Upload that ZIP as an HTML
game on itch.io. Use `--zip-output path/to/game.zip` to pick a different path.

## Publishing to GitHub Pages

`pygodide build .` produces a static site in `build/` (`index.html`, `boot.js`,
assets, and so on). [GitHub Pages](https://pages.github.com/) can host that
folder over HTTPS. Treat pygodide as a static site generator: commit your
**source**, build in CI, and publish only **`build/`**.

### Local check first

```bash
pygodide build .
pygodide serve .
# optional before shipping:
pygodide smoke . --verbose
```

Confirm the game works at [http://localhost:8000](http://localhost:8000). Prefer
keeping `build/` out of git (generate it on each deploy).

### Recommended: deploy with GitHub Actions

1. In the GitHub repo: **Settings → Pages → Build and deployment → Source:
   GitHub Actions**.
2. Add `.github/workflows/pages.yml` (adjust Python version or build flags as
   needed):

```yaml
name: Deploy game to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"

      - name: Install pygodide
        run: pip install pygodide

      - name: Build web app
        run: pygodide build . --clean
        # optional fixed canvas size:
        # run: pygodide build . --clean --canvas-width 1280 --canvas-height 720

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: build

      - id: deployment
        uses: actions/deploy-pages@v4
```

3. Push to `main`. The site will be at
   `https://<user-or-org>.github.io/<repo>/` (or your custom domain if
   configured).

Every push rebuilds from source, so deploys stay reproducible.

### Alternative: publish `build/` without Actions

Build locally, then publish only the contents of `build/` as the site root (for
example with [`gh-pages`](https://www.npmjs.com/package/gh-pages)):

```bash
pygodide build . --clean
npx gh-pages -d build
```

Or copy `build/*` onto a `gh-pages` branch manually. CI is usually easier to
keep up to date.

## Still stuck?

If you've worked through the sections above and a real part of your game still
will not build, load, or run in the browser, please
[open an issue](https://github.com/Elan456/pygodide/issues/new?template=conversion-failure.yml)
using the **My project didn't convert** template.

That format keeps reports easy to act on. Please include:

1. **What happened?**: what you ran, what you expected, and what you saw
   instead (browser behavior, error overlay text, and so on)
2. **Build log**: the full contents of `build/pygodide-build.log` (or
   `build/pygodide-smoke.log` if the failure came from `pygodide smoke`)
3. **Link to your project** (optional): a repo, gist, or zip so we can reproduce
4. **Anything else** (optional): browser console errors (F12 → Console),
   screenshots, or a smaller repro case

Run `pygodide smoke . --verbose` before filing if you have not already; the
smoke log often captures browser-side failures that a plain build log does not.