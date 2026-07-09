# Architecture

The pipeline goes from local development through CI and Cloud Build into Vertex
AI for GPU work, with artifacts in GCS / W&B and serving on Cloud Run: data
versioning (DVC), LoRA training with Hydra configs, experiment tracking and
model registry in W&B, model release to GCS, FastAPI serving, monitoring with
alerts, and two automation loops — **A** auto-deploy (W&B webhook → GitHub
Actions → new Cloud Run revision + smoke test) and **B** drift feedback (live
predictions → Evidently drift check).

<img src="../../reports/figures/architecture.jpg" alt="System architecture" width="700" height="332">

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
