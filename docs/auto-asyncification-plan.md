# Automatic Asyncification Plan

## Goal

Make `pygodide build` easier for new users by automatically adapting simple
sync Pygame entrypoints into async-compatible browser code.

Today users must manually:

1. Import `asyncio`.
2. Change `def main()` to `async def main()`.
3. Add `await asyncio.sleep(0)` inside the main game loop.

The proposed default behavior is:

- Detect whether the configured entrypoint is already async.
- If it is async, leave the app unchanged.
- If it is sync, try to asyncify the generated build copy automatically.
- Provide a CLI escape hatch to disable the automatic behavior.

The user's source files should not be modified.

## Proposed CLI

```bash
pygodide build . --no-auto-async
```

Default behavior:

```bash
pygodide build .
# auto asyncification is enabled
```

Recommended future config option:

```toml
[tool.pygodide]
auto-async = false
```

CLI flags should override project config.

## Viability

This is viable for a useful first version if the feature is intentionally
conservative.

The common beginner Pygame shape is easy to identify:

```python
def main():
    running = True
    while running:
        for event in pygame.event.get():
            ...

        pygame.display.update()
        clock.tick(60)
```

For that shape, pygodide can generate a browser-safe copy:

```python
import asyncio

async def main():
    running = True
    while running:
        for event in pygame.event.get():
            ...

        pygame.display.update()
        clock.tick(60)
        await asyncio.sleep(0)
```

The risky part is not changing `def` to `async def`; it is deciding where to
insert the yield. The feature should only transform code when it can identify a
likely game loop with high confidence.

## Non-Goals

- Do not mutate the user's project files.
- Do not promise to asyncify every Python program.
- Do not rewrite complex architecture in the first version.
- Do not hide the result. The build log should clearly say what happened.

## Detection Strategy

Use static source analysis before staging files into `build/`.

1. Resolve the configured entrypoint from the existing build plan.
2. Map the entrypoint module to a staged Python file.
   - `main:main` maps to `main.py`.
   - `game.main:start` maps to `game/main.py`.
3. Parse the file with `ast.parse`.
4. Find the target function by name.
5. If it is `ast.AsyncFunctionDef`, record `already async` and do nothing.
6. If it is `ast.FunctionDef`, inspect the function body for candidate loops.

Candidate loops for MVP:

- A `while` loop inside the entrypoint function.
- The loop body contains at least one Pygame/display/frame signal, such as:
  - `pygame.event.get(...)`
  - `pygame.display.update(...)`
  - `pygame.display.flip(...)`
  - `clock.tick(...)`

If no candidate loop is found, do not transform. Emit a warning with the manual
async instructions.

## Transformation Strategy

Perform the transformation on the staged build copy, not the source file.

Suggested module:

```text
pygodide/asyncify.py
```

Suggested API:

```python
@dataclass(frozen=True)
class AsyncifyResult:
    changed: bool
    status: Literal["already-async", "changed", "skipped"]
    message: str
    relative_path: str | None = None


def asyncify_entrypoint(build_plan: BuildPlan, output_dir: Path) -> AsyncifyResult:
    ...
```

Implementation outline:

1. Copy staged files as today.
2. If auto async is enabled, inspect and transform the copied entrypoint file in
   `build/`.
3. Add `import asyncio` if the module does not already import it.
4. Convert the entrypoint `FunctionDef` to `AsyncFunctionDef`.
5. Insert `await asyncio.sleep(0)` near the end of the selected game loop body.
  - Maybe you could just put an await like this in all while loops detected
6. Write the transformed file back to the build output.
7. Add the asyncification result to console output and `pygodide-build.log`.
  - Include the entire contents of the modified file in the log

Using `ast` plus `ast.unparse` is acceptable for the generated build copy,
because formatting changes would not touch the user's source. If preserving
comments in the generated copy becomes important, consider adding LibCST later.

## Build Pipeline Change

Current build flow:

```text
build_plan_for_source
collect_requirements
build_install_plan
copy_staged_files
write index.html
write boot.js
```

Proposed flow:

```text
build_plan_for_source
collect_requirements
build_install_plan
copy_staged_files
maybe asyncify staged entrypoint
write index.html
write boot.js
```

`boot.js` can stay mostly unchanged because generated startup Python already
awaits the entrypoint when it returns an awaitable.

## Logging

The build log should include one of:

```text
Auto async: already async (main:main)
Auto async: transformed main.py, inserted await asyncio.sleep(0)
Auto async: skipped main.py, no safe game loop found
Auto async: disabled by --no-auto-async
```

For skipped transformations, include the exact manual guidance:

```text
Make the entrypoint async and add await asyncio.sleep(0) once per frame.
```

## Tests

Add focused unit tests for `pygodide.asyncify`:

- Leaves `async def main()` unchanged.
- Converts `def main()` containing a simple `while running` Pygame loop.
- Adds `import asyncio` when missing.
- Does not duplicate `import asyncio`.
- Inserts only one `await asyncio.sleep(0)`.
- Skips a sync entrypoint with no recognizable loop.
- Skips when the entrypoint module file cannot be resolved.

Add CLI/build tests:

- `pygodide build` asyncifies by default.
- `pygodide build --no-auto-async` leaves sync source staged as-is.
- Build output includes the asyncification status.
- `pygodide-build.log` includes the asyncification status.

Add smoke fixture coverage:

- A deliberately sync beginner-style Pygame target that only works after
  asyncification.

## Risks

- False positives could change code behavior by yielding inside a loop that is
  not the game loop.
- False negatives will leave some users with the current manual step.
- `ast.unparse` changes formatting in generated files.
- Apps with helper-based architecture may put the loop outside the entrypoint.
- Apps using `time.sleep`, `pygame.time.wait`, or CPU-heavy work may still block
  the browser after asyncification.

The right tradeoff is to prefer false negatives over false positives. If pygodide
is not confident, it should skip the transform and explain the manual fix.

## Rollout Plan

### Phase 1: Conservative MVP

- Implement static detection for direct entrypoint loops.
- Transform only the generated build copy.
- Add `--no-auto-async`.
- Log every decision.
- Keep manual docs as fallback.

### Phase 2: Better Coverage

- Detect one-hop helper loops called by the entrypoint.
- Recognize more Pygame frame patterns.
- Add `[tool.pygodide].auto-async`.
- Add richer diagnostics explaining why a transform was skipped.

### Phase 3: Validation

- Run generated output through smoke tests.
- Consider warning when known blocking calls remain.
- Consider exposing a `pygodide asyncify --check` command for diagnostics only.

## Recommendation

Build this feature, but ship it as a conservative best-effort transform. It
should be enabled by default because it improves the beginner path, but it must
be transparent, logged, and easy to disable with `--no-auto-async`.
