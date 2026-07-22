# AGENTS.md

The contents of this file are for human contributors as well as the AI tools
leveraged by those human contributors for working on this project.

This file is mostly handwritten and should act as the north star for
guiding the project.

## Project

For an overview of the project, read the `README.md` and the `docs/index.md`.

The goal of the project is to create a dead-simple tool for beginner Python
developers to publish their games easily, while also exposing options for more
experienced developers to tailor the tool to their needs.

## AI-Rules

- Always acknowledge that you have read this file with "I've read the AGENTS.md"
  at the start of any chat or task involving the project.
- Never edit this file (AGENTS.md) even if told to do so explicitly.
    - Exception: Running a grammar pass (don't change any semantics)
- Never use any `git` commands.
    - `git log` and `git diff` are okay
- If you want to make temp output files or reports, name them with a leading "~" so they get ignored by git automatically. For example: ~analysis_report.md.

### Backwards-Compatibility

The project follows [semver](https://semver.org/) versioning rules, but those
rules only apply to the user-facing CLI. In practice, this means that every
minor and patch release must not introduce breaking changes to the user-facing
CLI, but can change anything around the internal interfaces.

### User-facing CLI

| Command | Role |
| --- | --- |
| `pygodide build` | Bundle a project into a webapp, resolve deps, optional auto-async, render `index.html` / `boot.js` |
| `pygodide serve` | Serve a built app |
| `pygodide smoke` | Build (and optionally browser-test) an app or suite of apps |

Typer definitions in `pygodide/cli/main.py` are the source of truth for CLI help
and the docs site CLI reference (`mkdocs-typer2` + Zensical).

## Layout

```text
pygodide/
  cli/           # Typer surface (main.py) + runners (runners.py)
  builder/       # plan, pipeline, zip, display_size (not named "build": that is the output dir)
  asyncify/      # AST transform of simple sync Pygame loops
  smoke/         # manifests, suite, Playwright
  dep_handling/  # collect requirements + Pyodide/micropip install plan
  logs.py        # shared build/smoke log files (not under builder)
  rendering.py   # Jinja → index.html / boot.js
  serving.py     # HTTP serve (CLI forever + ephemeral smoke server)
  project_config.py / pyproject.py
  templates/
tests/           # unit tests
test_targets/    # fixture apps + testing_manifest.yaml (see test_targets/README.md)
docs/            # Zensical site
benchmarks/      # cross-runtime FPS harness (not part of the CLI)
```

### Code style

- Target Python 3.11+. Ruff for format and lint (`uv run ruff format`, `uv run ruff check`).
- Prefer small modules with one clear job over mega-files.
- Frozen dataclasses for config/plan types.
- Typer options stay in `cli/main.py`; side effects live in `cli/runners.py`.

### Docs and prose

- Docs site: Zensical (`zensical.toml`, `docs/`). CLI reference is generated from
  Typer via `mkdocs-typer2`.
- After CLI help/`short_help` changes that affect generated docs, rebuild with
  `uv run zensical build --clean` when verifying the site (Zensical can cache
  pages that do not change on disk).
- Prefer normal ASCII punctuation in repo prose.
- Don't overuse **bold** and *italics*.
- Keep contributor-facing docs close to the code they describe (e.g.
  `test_targets/README.md` for the fixture suite).
- Do not use the word "staged" (or "staging") for files copied into the build.
  It is easily confused with git staging. Prefer "copied into the build",
  "packaged", or "included in the build" in docs, comments, logs, and errors.
- Prefer short, plain language. Say what is happening and what to do next; avoid jargon, log-style prefixes, and    
  parenthetical asides when a clearer main sentence works.

### Debuggability

Many novice developers will be using this tool. It is extremely important that
pygodide prioritizes easy-to-read error messages, obvious failure modes, and
clear warnings. The pygodide window should never just crash or freeze; it should
always give a helpful error message that is shown clearly on the webpage.
Anything that makes pygodide easier to use, or easier to figure out why an app
won't start on the web, should be prioritized.

### Dependencies

- Runtime deps: `[project].dependencies`.
- Browser smoke optional extra: `[project.optional-dependencies].smoke`
  (Playwright). Version is pinned there once.
- Dev group includes `pygodide[smoke]` so `uv sync --dev` gets the same
  Playwright pin. Do not duplicate the Playwright version string in `dev`.
- End users: `pip install 'pygodide[smoke]'` then `playwright install chromium`.
- Unit tests should not require a Chromium install; real browser smoke does.

## Workflows

### Dev setup

```bash
uv sync --dev
uv run playwright install chromium   # only if running real smoke / benchmarks
```

### Checks (same spirit as CI)

```bash
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

### Smoke

- One project: `uv run pygodide smoke path/to/app`
- Fixture suite: `uv run pygodide smoke test_targets --suite`
- `--build-only`: suite/pipeline without Playwright (still applies manifests,
  cleans, builds, smoke logs). Not a synonym for bare `pygodide build` on each
  folder; manifests can override app/deps/auto-async.
- Fixture schema and how to add targets: `test_targets/README.md`.

### Auto-async

Build-time AST rewrite for simple sync game loops (yield with
`await asyncio.sleep(1 / (fps * 2))`). Prefer improving detection/transform
carefully; unsafe transforms should skip with a clear message pointing at manual
async guidance.

### Writing a test_target

- Use an FPS of 120 to ensure it feels smooth.
- Write at the edge of pygodide's support so the fixtures act as good regression
  tests.
- Keep the code simple and easy to follow so users can read them as examples.
- Avoid writing for pygodide; write primarily for the local case to imitate what
  most real-world target Python projects will look like. Pygodide should bend to
  the project, not the other way around.

## What "done" looks like

- Behavior matches the product goals (build/serve/smoke stay reliable).
- Names and messages stay clear to game authors, not only to us.
- Docs/README/`test_targets` guidance updated when contributors need to know
  about behavior changes.

## Release Notes

- When asked to generate release notes, look at all of the code changes between the current head and the last tagged commit.
- Write a concise bulleted list of changes.
- Any breaking changes to the user CLI or how configuration files (e.g. the user's pyproject.toml file) will be interpreted should be put in a "Breaking Changes" section at the top.

Example Release Notes:

0.1.2

- Detect hung games that never yield and show fix guidance on the page
- Re-show hang help after ready if yielding stops (soft stalls)
- Smarter auto canvas size (prefer playable set_mode, ignore tiny/NOFRAME dummies)
- Make crash error panels scrollable and selectable
- Use Hack font for the loader by default
- Stop nesting previous zip builds into the next zip
- Smoke support for expected hang warnings (async_hang fixture)
- Docs and dependency bumps