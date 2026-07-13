from pathlib import Path

from pygodide.asyncify import asyncify_entrypoint
from pygodide.builder.plan import BuildPlan


def test_asyncify_leaves_async_entrypoint_unchanged(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        "async def main():\n    return None\n",
    )
    original_source = (tmp_path / "main.py").read_text(encoding="utf-8")

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is False
    assert result.status == "already-async"
    assert result.message == "Auto async: already async (main:main)"
    assert (tmp_path / "main.py").read_text(encoding="utf-8") == original_source


def test_asyncify_converts_simple_pygame_while_loop(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import pygame

def main():
    running = True
    clock = pygame.time.Clock()
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        pygame.display.update()
        clock.tick(60)
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    transformed_source = (tmp_path / "main.py").read_text(encoding="utf-8")
    assert result.changed is True
    assert result.status == "changed"
    assert result.message == (
        "Auto async: transformed main.py, inserted await asyncio.sleep(1 / (60 * 2))"
    )
    assert "import asyncio" in transformed_source
    assert "async def main():" in transformed_source
    assert "await asyncio.sleep(1 / (60 * 2))" in transformed_source


def test_asyncify_does_not_duplicate_asyncio_import(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import asyncio
import pygame

def main():
    while True:
        pygame.display.flip()
""".lstrip(),
    )

    asyncify_entrypoint(build_plan, tmp_path)

    transformed_source = (tmp_path / "main.py").read_text(encoding="utf-8")
    assert transformed_source.count("import asyncio") == 1


def test_asyncify_inserts_only_one_asyncio_sleep(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import pygame

def main():
    while True:
        pygame.display.flip()
""".lstrip(),
    )

    asyncify_entrypoint(build_plan, tmp_path)
    asyncify_entrypoint(build_plan, tmp_path)

    transformed_source = (tmp_path / "main.py").read_text(encoding="utf-8")
    assert transformed_source.count("await asyncio.sleep(1 / (60 * 2))") == 1


def test_asyncify_skips_sync_entrypoint_without_safe_loop(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
def main():
    while True:
        print("busy")
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is False
    assert result.status == "skipped"
    assert "no safe game loop found in the entrypoint" in result.message
    assert "Make the entrypoint async" in result.message
    assert "async def main" not in (tmp_path / "main.py").read_text(encoding="utf-8")


def test_asyncify_skips_when_helper_has_no_recognizable_loop(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
def main():
    prepare()

def prepare():
    print("ready")
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.status == "skipped"
    assert "helper functions were called but none contain" in result.message


def test_asyncify_converts_helper_game_loop_one_hop(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import pygame

def main():
    run_game()

def run_game():
    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return
        pygame.display.update()
        clock.tick(60)
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    transformed_source = (tmp_path / "main.py").read_text(encoding="utf-8")
    assert result.changed is True
    assert result.status == "changed"
    assert "async def main():" in transformed_source
    assert "await run_game()" in transformed_source
    assert "async def run_game():" in transformed_source
    assert transformed_source.count("await asyncio.sleep(1 / (60 * 2))") == 1


def test_asyncify_skips_when_multiple_helper_loops_are_called(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import pygame

def main():
    run_left()
    run_right()

def run_left():
    while True:
        pygame.display.flip()

def run_right():
    while True:
        pygame.display.update()
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is False
    assert result.status == "skipped"
    assert "multiple helper game loops found" in result.message


def test_asyncify_converts_loop_that_uses_event_pump(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import pygame

def main():
    while True:
        pygame.event.pump()
        pygame.display.flip()
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is True
    assert "await asyncio.sleep(1 / (60 * 2))" in (tmp_path / "main.py").read_text(
        encoding="utf-8"
    )


def test_asyncify_warns_about_module_level_asyncio_run(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import asyncio
import pygame

async def main():
    while True:
        pygame.display.update()
        await asyncio.sleep(1 / (60 * 2))

asyncio.run(main())
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert any("module-level asyncio.run()" in warning for warning in result.warnings)


def test_asyncify_warns_about_blocking_calls_in_game_loop(tmp_path):
    build_plan = _write_package_app(
        tmp_path,
        """
import pygame
import time

def main():
    while True:
        pygame.event.get()
        time.sleep(0.01)
        pygame.display.update()
""".lstrip(),
    )

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is True
    assert any("time.sleep" in warning for warning in result.warnings)


def test_asyncify_skips_when_entrypoint_module_file_is_not_found(tmp_path):
    build_plan = _build_plan(tmp_path, package_files=["helpers.py"])

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is False
    assert result.status == "skipped"
    assert "entrypoint module file was not found" in result.message
    assert result.relative_path == "main.py"


def test_asyncify_skips_when_entrypoint_module_file_is_not_in_package(tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    pass\n", encoding="utf-8")
    build_plan = _build_plan(tmp_path, package_files=["helpers.py"])

    result = asyncify_entrypoint(build_plan, tmp_path)

    assert result.changed is False
    assert result.status == "skipped"
    assert "not included in the build package" in result.message
    assert result.relative_path == "main.py"


def _write_package_app(
    output_dir: Path,
    source: str,
    *,
    relative_path: str = "main.py",
) -> BuildPlan:
    output_path = output_dir / relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(source, encoding="utf-8")
    return _build_plan(output_dir, package_files=[relative_path])


def _build_plan(output_dir: Path, *, package_files: list[str]) -> BuildPlan:
    return BuildPlan(
        source_dir=output_dir,
        output_dir=output_dir,
        package_files=package_files,
        entry_module="main",
        entry_function="main",
        app_source="default",
        package_files_source="test",
        title="Test App",
        canvas_width=800,
        canvas_height=600,
        canvas_layout="fixed",
        canvas_aspect_found=False,
        canvas_aspect_source=None,
        canvas_aspect_width=800,
        canvas_aspect_height=600,
        python_path_entries=["/"],
    )
