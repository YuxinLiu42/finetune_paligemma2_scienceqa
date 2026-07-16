Generating the docs
----------

Use [mkdocs](http://www.mkdocs.org/) structure to update the documentation.

The MkDocs config lives at `docs/mkdocs.yaml` (not the repo root), so a bare
`mkdocs build` / `mkdocs serve` fails with "config file does not exist" — pass
the config explicitly or use the invoke tasks:

Build locally with:

    uv run inv build-docs    # = mkdocs build --config-file docs/mkdocs.yaml --site-dir build

Serve locally with:

    uv run inv serve-docs    # = mkdocs serve --config-file docs/mkdocs.yaml
