"""Task definitions for invoke."""

import os
import shutil
from pathlib import Path

from invoke import Context, task

WINDOWS = os.name == "nt"
PROJECT_NAME = "scipali"
PYTHON_VERSION = "3.11.0"


# Environment commands
@task
def requirements(ctx: Context) -> None:
    """Install the locked runtime dependencies."""
    ctx.run("uv sync --locked", echo=True, pty=not WINDOWS)


@task
def dev_requirements(ctx: Context) -> None:
    """Install the locked dev dependencies (the same set CI uses for tests)."""
    ctx.run("uv sync --locked --dev --group monitoring", echo=True, pty=not WINDOWS)


# Project commands
@task
def preprocess_data(ctx: Context) -> None:
    """Download and preprocess data."""
    ctx.run(
        f"uv run python -m {PROJECT_NAME}.data.data download",
        echo=True,
        pty=not WINDOWS,
    )
    ctx.run(
        f"uv run python -m {PROJECT_NAME}.data.data preprocess",
        echo=True,
        pty=not WINDOWS,
    )


@task
def train(ctx: Context, config: str = "train") -> None:
    """Train model."""
    ctx.run(
        f"uv run python src/{PROJECT_NAME}/models/train.py --config-name {config}",
        echo=True,
        pty=not WINDOWS,
    )


@task
def test(ctx: Context) -> None:
    """Run tests."""
    ctx.run("uv run coverage run -m pytest tests/", echo=True, pty=not WINDOWS)
    ctx.run("uv run coverage report -m -i", echo=True, pty=not WINDOWS)


@task
def lint(ctx: Context) -> None:
    """Run the same checks as the linting CI workflow."""
    ctx.run("uv run ruff check .", echo=True, pty=not WINDOWS)
    ctx.run("uv run ruff format . --check", echo=True, pty=not WINDOWS)
    ctx.run("uv run mypy .", echo=True, pty=not WINDOWS)


@task
def clean(ctx: Context) -> None:
    """Remove caches and build artifacts (keeps data, checkpoints, run logs)."""
    dirs = [".pytest_cache", ".mypy_cache", ".ruff_cache", "htmlcov", "build", "dist"]
    files = [".coverage", "coverage.xml", "profile_output.prof"]
    removed = 0
    for name in dirs:
        path = Path(name)
        if path.is_dir():
            shutil.rmtree(path)
            print(f"removed {name}/")
            removed += 1
    for name in files:
        path = Path(name)
        if path.is_file():
            path.unlink()
            print(f"removed {name}")
            removed += 1
    for cache in Path(".").rglob("__pycache__"):
        if ".venv" not in cache.parts:
            shutil.rmtree(cache)
            removed += 1
    print(f"clean: removed {removed} items")


@task
def docker_build(ctx: Context, progress: str = "plain") -> None:
    """Build docker images."""
    ctx.run(
        f"docker build -t train:latest . -f"
        f" dockerfiles/train.dockerfile --progress={progress}",
        echo=True,
        pty=not WINDOWS,
    )
    ctx.run(
        f"docker build -t api:latest . -f "
        f"dockerfiles/api.dockerfile --progress={progress}",
        echo=True,
        pty=not WINDOWS,
    )
    ctx.run(
        f"docker build -t predict:latest . -f "
        f"dockerfiles/predict.dockerfile --progress={progress}",
        echo=True,
        pty=not WINDOWS,
    )


# Serving commands
@task
def serve_api(ctx: Context, checkpoint: str = "checkpoints/adapter-production") -> None:
    """Serve the FastAPI app locally on port 8000 (CPU, local adapter)."""
    ctx.run(
        "uv run uvicorn scipali.serving.api:app --port 8000",
        env={"CHECKPOINT_PATH": checkpoint, "PREDICT_DEVICE": "cpu"},
        echo=True,
        pty=not WINDOWS,
    )


@task
def figures(ctx: Context) -> None:
    """Regenerate all report figures from the committed eval JSONs."""
    viz = f"uv run python -m {PROJECT_NAME}.models.visualize"
    commands = [
        f"{viz} subject-accuracy reports/eval/production_eval_results.json",
        f"{viz} sweep-comparison reports/eval/sweep3_summary.json",
        f"{viz} sweep-comparison reports/eval/sweep2_summary.json",
        f"{viz} pred-lengths reports/eval/production_eval_results.json",
        f"{viz} prune-curve reports/eval/prune_results.json",
        # these two also read the DVC-pulled processed split:
        f"{viz} topic-accuracy reports/eval/production_eval_results.json",
        f"{viz} error-samples reports/eval/production_eval_results.json",
    ]
    for command in commands:
        ctx.run(command, echo=True, pty=not WINDOWS)


# Documentation commands
@task
def build_docs(ctx: Context) -> None:
    """Build documentation."""
    ctx.run(
        "uv run mkdocs build --config-file docs/mkdocs.yaml --site-dir build",
        echo=True,
        pty=not WINDOWS,
    )


@task
def serve_docs(ctx: Context) -> None:
    """Serve documentation."""
    ctx.run(
        "uv run mkdocs serve --config-file docs/mkdocs.yaml", echo=True, pty=not WINDOWS
    )
