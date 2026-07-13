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

Use a different port with `pygodide serve . --port 3000`.

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

## Make the game async-compatible

Pygame games need to yield to the browser event loop. Pygodide tries to do this
automatically during `pygodide build` by inserting `await asyncio.sleep(0)` into
simple `while` game loops in your entrypoint (or a helper it calls directly).

Check whether that worked:

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
3. Add `await asyncio.sleep(0)` once per frame inside the main loop
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
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((0, 0, 0))
        pygame.display.update()
        clock.tick(60)
        await asyncio.sleep(0)

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

Use simple paths relative to your project root, the same way you would when
running the game locally from that directory:

```python
pygame.image.load("assets/sprites/player.png")
pygame.mixer.Sound("sounds/jump.ogg")
```

Pygodide stages those files into the browser build and sets the working
directory to the project root before your app starts, so `sounds/...` and
`assets/...` usually work without extra configuration.

If your project root contains a favicon file (`favicon.svg`, `favicon.png`,
`favicon.ico`, and a few other common names), the build uses it for the hosted
app tab icon. Otherwise pygodide ships a small default favicon.

`python-path` does **not** affect asset loading. It only changes where Python
looks for modules to `import`. If an image or sound fails to load, fix the file
path or make sure the file is included in the build; do not add its folder to
`python-path`.

The [asset maze](https://github.com/Elan456/pygodide/tree/main/test_targets/asset_maze)
example loads nested assets from several modules using plain relative paths.

### Python path

The default is `python-path = ["."]`, which is enough for most projects.

`python-path` adds folders to `sys.path` before pygodide imports your entry
function. Only add entries beyond `"."` when your **imports** need them.

**You usually do not need extra entries for:**

- `sounds/`, `assets/`, `data/`, and other asset folders opened by path string
- normal packages such as `game/` imported as `import game` or
  `from game.loader import ...`
- dependencies installed with `requirements.txt` or `[project].dependencies`

**Add another `python-path` entry when you import loose modules from a folder
that is not a package**, for example:

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

If those imports work locally only because you run with `PYTHONPATH=src:lib`,
mirror that in `pyproject.toml`:

```toml
[tool.pygodide]
python-path = [".", "src", "lib"]
```

Each entry is relative to the project root. `"."` should stay first for typical
layouts.

**Prefer fixing imports over growing `python-path`:** if `lib/helpers.py` can be
imported as `from lib.helpers import load_level` instead, add `lib/__init__.py`
(or make `lib` a regular package) and keep the default `python-path = ["."]`.

**`src/` layouts:** if your game code lives under `src/` and imports assume that
directory is on the path, add `"src"` rather than moving files around.

### `pyproject.toml` reference

Recommended when your project already has a `pyproject.toml`:

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
canvas-width = 800
canvas-height = 600
# python-path = [".", "src", "lib"]  # only when imports need extra roots
dependencies = ["pyyaml"]
dependency-groups = ["web"]
```

| Field | Purpose |
| --- | --- |
| `app` | Entry function (`module:callable`). Defaults to `main:main`. |
| `auto-async` | Enable/disable automatic game-loop conversion. Defaults to `true`. |
| `include` | Files to stage into the build. If omitted, pygodide auto-discovers files (excluding `.git`, `.github`, `.venv`, `build`, `pyproject.toml`, and similar tooling dirs). |
| `title` | HTML page title. Defaults to the project directory name. |
| `canvas-width`, `canvas-height` | Fixed HTML canvas size in pixels. If **both** are omitted (and not passed on the CLI), the canvas fills the browser viewport at boot. Override with `pygodide build . --canvas-width W --canvas-height H`. |
| `python-path` | Folders added to `sys.path` for imports. Defaults to `["."]`. See [Python path](#python-path). |
| `dependencies` | Extra browser-only packages not listed under `[project]`. |
| `dependency-groups` | Named dependency groups to include in the web build. |

The [numpy particles](https://github.com/Elan456/pygodide/tree/main/test_targets/numpy_particles)
example uses `[project].dependencies` for `numpy`, `pygame-ce`, and
`fastquadtree`, plus `app = "main:web_main"` for a separate browser entry
function.

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

### Tips

- **Paths**: pygodide uses relative asset URLs (`./boot.js`, and so on), so
  project pages under `/<repo>/` and **custom domains** work without extra
  base-path config. A custom DNS name is not a special case.
- **What gets staged**: auto-discovery should only pick up game assets and
  source. Tooling trees such as `.git` and `.github` are skipped so the browser
  does not try to `fetch` CI workflow files that Pages will not serve.
- **Canvas size**: match `pygame.display.set_mode`, or pass
  `--canvas-width` / `--canvas-height`, or leave both unset to fill the
  viewport.
- **First load**: the browser downloads Pyodide and packages from the CDN; that
  can take a while and is unrelated to Pages misconfiguration.
- **Smoke in CI**: optional and heavier (Playwright + Chromium). Many projects
  run smoke only on pull requests or releases.
- **Public site**: everything under `build/` is public; do not ship secrets.
- **itch.io vs Pages**: same `build/` idea. itch uses `pygodide build . --zip`;
  Pages serves the `build/` directory continuously from git/CI.

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