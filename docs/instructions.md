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
| You are not sure what failed | [Run a smoke test](#check-your-build-with-a-smoke-test) |

## Check your build with a smoke test

`pygodide smoke` builds your app and opens it in a headless browser. Use it to
catch problems before you debug in a real browser:

```bash
pygodide smoke .
```

By default you only see pass/fail on the console. For full build and smoke
output:

```bash
pygodide smoke . --verbose
```

Either way, the full log is saved to `build/pygodide-smoke.log`. Look there for
dependency resolution, auto-async status, and smoke-test errors.

To validate without launching a browser:

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

- [ball bouncing](https://github.com/Elan456/pygodide/blob/main/test_targets/ball_bouncing/main.py) — already-async game
- [not async](https://github.com/Elan456/pygodide/blob/main/test_targets/not_async/main.py) — sync loop that auto-asyncifies at build time
- [numpy particles](https://github.com/Elan456/pygodide/blob/main/test_targets/numpy_particles/main.py) — custom entry point and extra dependencies

## Configure your project

### Entry point

If your game does not start at `main()` in `main.py`, tell pygodide which
function to run. The value uses `module:callable` format — a Python import path,
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
python-path = [".", "vendor"]
dependencies = ["pyyaml"]
dependency-groups = ["web"]
```

| Field | Purpose |
| --- | --- |
| `app` | Entry function (`module:callable`). Defaults to `main:main`. |
| `auto-async` | Enable/disable automatic game-loop conversion. Defaults to `true`. |
| `include` | Files to stage into the build. If omitted, pygodide auto-discovers files (excluding `.venv`, `build`, `pyproject.toml`, etc.). |
| `title` | HTML page title. Defaults to the project directory name. |
| `canvas-width`, `canvas-height` | Canvas size in pixels. Default `800`×`600`. |
| `python-path` | Entries added to `sys.path` before importing your app. |
| `dependencies` | Extra browser-only packages not listed under `[project]`. |
| `dependency-groups` | Named dependency groups to include in the web build. |

The [numpy particles](https://github.com/Elan456/pygodide/tree/main/test_targets/numpy_particles)
example uses `[project].dependencies` for `numpy`, `pygame-ce`, and
`fastquadtree`, plus `app = "main:web_main"` for a separate browser entry
function.