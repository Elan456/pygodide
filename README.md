# pygodide

**BETA (Everything is subject to change)**

Pronounced "pie-go-died",
pygodide is a tool for converting pygame projects into web applications using Pyodide.
It provides a simple command line interface and works by analyzing your code and
asset files and then building them together with some web-specific glue code to make everything work in the browser.

Thanks to Pyodide, pygodide supports far more Python packages than just pygame.

**Documentation**: [https://elan456.github.io/pygodide/](https://elan456.github.io/pygodide/)

## Install

```bash
pip install pygodide
```

```bash
git clone https://github.com/Elan456/pygodide.git
cd pygodide
uv sync --dev
```

## Quick Start

```bash
pygodide build /path/to/your/pygame/project --serve
```

That's it! Open http://localhost:8000 in a web browser to see your app running.
Currently only supports flat projects. The vision is to support any arbitrary 
pygame project. 

You can also add dependencies directly from the CLI:

```bash
pygodide build /path/to/your/pygame/project \
  --dep pygame-ce \
  --dep fastquadtree
```

## Dependency Sources

`pygodide build` now merges dependencies from these sources:

1. `requirements.txt`
2. `[project].dependencies`
3. `[tool.pygodide].dependencies`
4. dependency groups named in `[tool.pygodide].dependency-groups`
5. repeated `--dep` flags

Later sources override earlier ones when the same package is declared more than
once. The build command prints the sources it used and whether each dependency
was assigned to `pyodide.loadPackage(...)` or `micropip.install(...)`.

Example:

```toml
[project]
name = "my-game"
version = "0.1.0"
dependencies = ["numpy>=1.26"]

[dependency-groups]
web = ["pygame-ce"]

[tool.pygodide]
app = "main:web_main"
dependencies = ["fastquadtree"]
dependency-groups = ["web"]
```

## Development

Install the local hooks once after cloning:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Run the same checks as CI locally:

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

## Proof of Concept

`test_targets/ball_bouncing` contains a small Pygame app. 

Using the following command, you can build and serve the app in a web browser:

```bash
pygodide build test_targets/ball_bouncing/src --serve
```

You'll get the output of:

```bash
Serving /home/ethan/Projects/pygodide/test_targets/ball_bouncing/build at http://localhost:8000
```

Open http://localhost:8000 in a web browser to see the app running. You should see a bouncing ball!
Press the arrow keys to accelerate the ball in different directions. 
