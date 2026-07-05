# pygodide

**pygodide** turns Pygame projects into browser apps using [Pyodide](https://pyodide.org/).
It bundles your code and assets, installs Python dependencies in the browser, and
generates the HTML and JavaScript needed to run your game on the web.

## Install

```bash
pip install pygodide
```

## Get started in 30 seconds

From your project root:

```bash
pygodide build .
pygodide serve .
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

Pygodide looks for `main()` in `main.py`, reads dependencies from
`requirements.txt` or `pyproject.toml`, and auto-converts simple game loops for
the browser. That covers most small projects without extra setup.

When it works, your game is a normal web page — easy to host, link, and share.
`pygodide build . --zip` produces an itch.io-ready upload if you want to reach
more players without a separate web port. See
[Publishing to itch.io](instructions.md#publishing-to-itchio) in the instructions.

## Need more help?

See the **[Instructions](instructions.md)** guide for:

- troubleshooting when the quick start does not work
- setting a custom entry point or dependencies
- making your game async-compatible
- running `pygodide smoke` to check a build before debugging in the browser

## Common commands

| Command | What it does |
| --- | --- |
| `pygodide build .` | Bundle your project into `build/` |
| `pygodide serve .` | Serve the built app locally (default port `8000`) |
| `pygodide serve . --port 3000` | Serve on a different port |
| `pygodide smoke .` | Build and test in a headless browser |
| `pygodide build . --app game:start` | Use a different entry function |
| `pygodide build . --dep numpy` | Add an extra dependency for this build |
| `pygodide build . --zip` | Build and create an itch.io-ready ZIP |

Build output is logged to `build/pygodide-build.log`. Smoke tests also write
`build/pygodide-smoke.log`.

## Examples

Working sample projects live in the
[test_targets](https://github.com/Elan456/pygodide/tree/main/test_targets)
directory on GitHub, including:

- [ball bouncing](https://github.com/Elan456/pygodide/tree/main/test_targets/ball_bouncing) — minimal async Pygame game
- [not async](https://github.com/Elan456/pygodide/tree/main/test_targets/not_async) — sync loop converted automatically at build time
- [numpy particles](https://github.com/Elan456/pygodide/tree/main/test_targets/numpy_particles) — larger game with extra dependencies