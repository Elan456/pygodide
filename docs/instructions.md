# Instructions

The following page details the steps you need to take to effectively use pygodide to serve
your Pygame app on the web.

## 1. Creating an async loop

This step sounds scary, but it's actually pretty simple. When the game is running in the browser, we need it to
take small breaks to let the rest of the web page update properly.

To do so, we'll use a Python package called `asyncio`.


### 1.1 Install asyncio


```bash
pip install asyncio
```

```python
import asyncio
```


### 1.2 Make the entry point async

Then, we need to make your game's entry point async. This can be done by adding the keyword `async` to the definition.

```python
def main():

# Becomes

async def main():
```


### 1.3 Add an asyncio.sleep to the main loop

Finally, find the main loop of your game (typically `while True:`) and
add `await asyncio.sleep(0)` there.

### Example

Here's a minimal but complete example of async-ifying a Pygame game loop:

```python
# 1. Import asyncio so the game can yield control back to the browser.
import asyncio

import pygame


SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Async Pygame Example")


# 2. Make the game entry point async.
async def main():
    clock = pygame.time.Clock()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((0, 0, 0))

        # Draw and update your game here.
        pygame.draw.circle(screen, pygame.Color("white"), (400, 300), 40)

        pygame.display.update()
        clock.tick(60)

        # 3. Yield once per frame so the webpage can keep updating.
        # Keep the sleep duration at 0.
        await asyncio.sleep(0)
```

See the [bouncing ball](https://github.com/Elan456/pygodide/blob/main/test_targets/ball_bouncing/main.py) and [numpy particles](https://github.com/Elan456/pygodide/blob/main/test_targets/numpy_particles/main.py) examples for larger async-compatible games.

## 2. Declaring Entry Point and Dependencies

Pygodide needs you to declare which packages your app depends on so that pygodide can have pyodide install them in the user's browser. You can do so with a few different methods, but some are preferred over others.

Additionally, pygodide needs to know which function to call to start the game (the entry point). This can also be specified in a few different ways.

### pyproject.toml (Recommended)

If your project is already using a `pyproject.toml`, you can add a few more fields to give pygodide the entry point, dependencies, files, and display settings for your project.

Here is a complete example showing standard project dependencies plus every `[tool.pygodide]` field pygodide currently reads:

```toml
[project]
name = "my-game"
version = "0.1.0"
dependencies = [
    "pygame-ce",
    "numpy>=1.26",
    "pillow",
]

[dependency-groups]
web = [
    "fastquadtree",
]

[tool.pygodide]
app = "main:web_main"
include = ["main.py", "sprites/**", "sounds/**"]
title = "My Game"
canvas-width = 800
canvas-height = 600
python-path = [".", "vendor"]
dependencies = [
    "pyyaml",
]
dependency-groups = ["web"]
```

Pygodide looks for `pyproject.toml` in the root directory you pass to `pygodide build`.
For example, `pygodide build test_targets/numpy_particles` reads `test_targets/numpy_particles/pyproject.toml`.

The `numpy_particles` target uses this file for two things:

- `[project].dependencies` declares browser runtime packages: `numpy`, `pygame-ce`, and `fastquadtree`.
- `[tool.pygodide].app = "main:web_main"` tells pygodide to import `web_main` from `main.py` and run it as the app entry point.

#### Entry point

Use `[tool.pygodide].app` to choose the function pygodide should run:

```toml
[tool.pygodide]
app = "main:web_main"
```

The value must use `module:callable` format. For `main:web_main`, pygodide generates startup code equivalent to importing `web_main` from the `main` module and then calling it. If the function returns an awaitable, pygodide awaits it, so this works naturally with `async def web_main():`.

This is a Python import path, not a filename. Use `main:web_main`, not `main.py:web_main`.

If you do not set `app`, pygodide defaults to:

```toml
[tool.pygodide]
app = "main:main"
```

The CLI flag `--app` overrides `[tool.pygodide].app` for that build.

#### Dependencies

Pygodide merges dependencies from these sources, in this order:

1. `requirements.txt`
2. `[project].dependencies`
3. `[tool.pygodide].dependencies`
4. groups listed in `[tool.pygodide].dependency-groups`
5. repeated CLI `--dep` flags

Later sources override earlier sources when the same package name appears more than once. Package names are compared case-insensitively, and underscores are treated like hyphens. This means `numpy`, `NumPy`, and `numpy>=1.26` all refer to the same package for merging purposes.

This also applies inside a single list. In the current `numpy_particles` target, `numpy>=1.26` appears before `numpy`, so the later plain `numpy` entry wins and removes the `>=1.26` constraint. Prefer declaring each package only once unless you intentionally want a later entry to replace an earlier one.

Use `[project].dependencies` for normal runtime dependencies:

```toml
[project]
dependencies = [
    "pygame-ce",
    "numpy>=1.26",
    "fastquadtree",
]
```

Use `[tool.pygodide].dependencies` for extra browser-only dependencies you do not want in your normal project dependency list:

```toml
[tool.pygodide]
dependencies = [
    "pyyaml",
]
```

Use dependency groups when you want named dependency sets and then opt into them for the web build:

```toml
[dependency-groups]
web = [
    "pillow",
    "fastquadtree",
]

[tool.pygodide]
dependency-groups = ["web"]
```

All dependency entries must be strings in the normal Python requirement format, such as `"pygame-ce"`, `"numpy>=1.26"`, or `"pillow<12"`.

During the build, pygodide decides how to install each resolved dependency in the browser:

- `pygame-ce` is loaded with `pyodide.loadPackage(...)`.
- Other packages are installed with `micropip.install(...)`.

The build output prints the dependency sources it found, the final merged dependency list, and which installer each dependency will use.

#### Files and Assets

By default, pygodide auto-discovers files under your project directory and stages them into the browser filesystem. It excludes `pyproject.toml`, `testing_manifest.yaml`, `uv.lock`, and anything under `.venv`, `__pycache__`, or `build`.

If you set `[tool.pygodide].include`, pygodide stages only files matching those patterns:

```toml
[tool.pygodide]
include = ["main.py", "assets/**"]
```

Each include pattern must match at least one file. Use this when you want to keep development-only files out of the web build or when you need to explicitly include asset folders.

#### Display and Imports

These optional `[tool.pygodide]` fields customize the generated page and Python import path:

```toml
[tool.pygodide]
title = "My Game"
canvas-width = 1024
canvas-height = 768
python-path = [".", "vendor"]
```

- `title` sets the generated HTML page title. If omitted, pygodide creates a title from the project directory name.
- `canvas-width` and `canvas-height` set the Pygame canvas size in the generated HTML. Both must be integers. If omitted, pygodide uses `800` by `600`.
- `python-path` adds entries to `sys.path` before importing your app. Relative entries are resolved inside the browser filesystem. If omitted, pygodide uses the staged project root (`/` in the browser filesystem, equivalent to `"."` in your source project).

### No pyproject.toml

Without a `pyproject.toml`, pygodide will use default values or CLI-defined values.
It will check for a `requirements.txt` and add those dependencies to the dependency list.

For example, the [ball bouncing](https://github.com/Elan456/pygodide/tree/main/test_targets/ball_bouncing) example does not have a `pyproject.toml`, but it does have a `requirements.txt`, so those dependencies will be installed. The default entry point of `main:main` will also work because the main function in `main.py` is the actual entry point for that target.

You can still use the `--dep` and `--app` CLI options to configure the entry point and dependencies.
