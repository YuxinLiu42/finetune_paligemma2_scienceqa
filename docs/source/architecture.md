# Architecture

The pipeline goes from local development through CI and Cloud Build into Vertex
AI for GPU work, with artifacts in GCS / W&B and serving on Cloud Run.

```mermaid
flowchart TD
    dev["Local dev<br/>(Hydra configs, Lightning)"] -->|git push| gh["GitHub"]
    gh -->|"CI: ruff + pytest"| ci["GitHub Actions"]
    gh -->|"push trigger (api) · manual submit (train)"| cb["Cloud Build<br/>(amd64 images)"]
    cb --> ar["Artifact Registry<br/>paligemma-train / paligemma-api"]

    subgraph data["Data (DVC)"]
        hf["derek-thomas/ScienceQA<br/>(image subset)"] --> proc["processed splits<br/>train 6218 / val 2097 / test 2017"]
        proc --> gcs[("GCS DVC remote")]
    end

    ar -->|digest-pinned image| vertex["Vertex AI custom job (L4)<br/>baseline + W&B sweep + by-subject eval"]
    gcs -->|dvc pull| vertex
    vertex -->|adapters + metrics| wandb["W&B<br/>runs + model registry"]
    vertex -->|LoRA adapter| models[("GCS models/production/")]

    models -->|CHECKPOINT_PATH gs://| run["Cloud Run<br/>FastAPI /predict"]
    run --> ui["Streamlit frontend"]
    run --> mon["Cloud monitoring + alerts"]
```

## Key design choices

- **Secrets** live in Secret Manager; job specs carry only secret *names*, and
  jobs run as the compute service account (which holds `secretAccessor`).
- **Images are digest-pinned** at submit time — Vertex resolves `:latest` at
  container start, which can drift across a long Flex Start queue.
- **Serving reads the adapter from `gs://…/models/production`** at startup, so
  promoting a new model needs no redeploy — just re-copy the adapter and move
  the W&B `production` alias.
- **`val/accuracy` is the sweep metric**, not `val/loss`: the two disagree, and
  the task is scored on exact-match of the answer letter.
