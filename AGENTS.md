> Guidance for autonomous coding agents
> Read this before writing, editing, or executing anything in this repo.

# Relevant commands

* The project uses `uv` for management of virtual environments. This means:
  * To install packages, use `uv add <package-name>`.
  * To run Python scripts, use `uv run <script-name>.py`.
  * To run other commands related to Python, prefix them with `uv run `, e.g., `uv run <command>`.
* The project uses `pytest` for testing. To run tests, use `uv run pytest tests/`.
* The project uses `ruff` for linting and formatting:
    * To format code, use `uv run ruff format .`.
    * To lint code, use `uv run ruff check . --fix`.
* The project uses `invoke` for task management. To see available tasks, use `uv run invoke --list` or refer to the
    `tasks.py` file.
* The project uses `pre-commit` for managing pre-commit hooks. To run all hooks on all files, use
    `uv run pre-commit run --all-files`. For more information, refer to the `.pre-commit-config.yaml` file.
* The project's own pipeline is exposed as `typer` CLIs under `src/scipali/`, run with
    `uv run python -m scipali.<area>.<module> <command>` — e.g. `scipali.data.data preprocess`,
    `scipali.models.train`, `scipali.models.evaluate`, `scipali.models.optimize prune-sweep`,
    `scipali.serving.predict`, `scipali.monitoring.monitoring drift`. Multi-command modules
    (`optimize`, `monitoring`, `data`) require a subcommand — a bare module invocation fails.
* Commands are documented in TWO places that must stay in sync: the README's
    "Command guide" (the primary, exam-facing catalog with expected outputs) and
    `docs/source/usage.md` (the docs-site reference). When a command changes, grep for it
    and update both.

# Code style

* Follow existing code style.
* Keep line length within 120 characters.
* Use f-strings for formatting.
* Use type hints
* Do not add inline comments unless absolutely necessary.

# Documentation

* If the project has a `docs/` folder, update documentation there as needed.
* In this case the project will be using `mkdocs` for documentation. To serve the docs locally, use
    `uv run inv serve-docs` (= `uv run mkdocs serve --config-file docs/mkdocs.yaml`; the config is NOT
    at the repo root, so a bare `mkdocs serve` fails).
* In docs pages, embed images with markdown `![]()` syntax, never raw `<img>` tags — MkDocs
    rewrites relative paths only in markdown syntax, so raw tags 404 on the built site.
    Files referenced by docs pages must live inside `docs/source/` (MkDocs cannot serve
    files outside its `docs_dir`).
* Use existing docstring style.
* Ensure all functions and classes have docstrings.
* Use Google style for docstrings.
* Update this `AGENTS.md` file if any new tools or commands are added to the project.

# Repo-specific gotchas

* The train docker image is built MANUALLY (it installs a prebuilt wheel from `wheelhouse/`,
  which a bare CI checkout does not have). The `mlops-ci-train` Cloud Build trigger is
  disabled ON PURPOSE — do not "fix" CI by re-enabling it. Building the project in-image
  drops `scipali`'s subpackages; see the comment in `dockerfiles/train.dockerfile`.
* Hydra configs in `configs/` are plain files loaded by directory path — the folder is not a
  Python package.
* The pre-commit `check-added-large-files` cap is 5 MB — compress figures before adding
  (`reports/figures/` is the image home; the docs site needs its own copy under `docs/source/`).
* GPU work runs ONLY on Vertex AI (`europe-west4`, single L4, Flex Start queue) — there is no
  local GPU. GPU-only code paths (e.g. `optimize prune-finetune`) cannot be unit-tested;
  `mypy` is the main static guard for them.
