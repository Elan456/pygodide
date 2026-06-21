# pygodide

## Install

> pypi isn't available yet

```bash
git clone https://github.com/Elan456/pygodide.git
cd pygodide
uv sync
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