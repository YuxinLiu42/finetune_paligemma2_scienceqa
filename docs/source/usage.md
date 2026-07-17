# Usage

All commands assume the project environment is synced (`uv sync`). A fuller
command catalog — including CI, debugging, billing, and teardown, with
expected outputs — is the
[README's command guide](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa#command-guide).

## Data

```bash
# Download derek-thomas/ScienceQA (image questions) and preprocess the splits
uv run python -m scipali.data.data download
uv run python -m scipali.data.data preprocess --overwrite
dvc push   # publish processed data to the GCS remote
```

## Train (local)

```bash
uv run train trainer.wandb.enabled=true trainer.wandb.run_name=local-test
# smoke run — 1 train + 1 val batch, then exit:
uv run train trainer.fast_dev_run=true trainer.wandb.enabled=false
# profile the training loop (Lightning profiler, report printed at run end):
uv run train trainer.profiler=simple trainer.fast_dev_run=true trainer.wandb.enabled=false
```

Hyperparameters live in `configs/` (Hydra). The learning rate is derived from
`model.base_learning_rate` via a sqrt batch-size rule unless set explicitly.

## Train + sweep on Vertex AI

```bash
# baseline + N-trial W&B sweep + by-subject eval, on one L4 (Flex Start queue)
bash cloud/watch_job.sh                         # full run
SKIP_BASELINE=1 bash cloud/watch_job.sh         # sweep only
```

Explicit method (what the script wraps, minus retries, image digest-pinning,
and log streaming):

```bash
envsubst < cloud/vertex_config.template.yaml > cloud/vertex_config.yaml
gcloud ai custom-jobs create --region=europe-west4 --project=paligemma-scienceqa \
  --display-name=paligemma-train --config=cloud/vertex_config.yaml
gcloud ai custom-jobs stream-logs <job-id> --region=europe-west4
```

The eval and optimize jobs below use the same method with their own templates
(`vertex_eval.template.yaml`, `vertex_optimize.template.yaml`). Inside the
container the job runs `cloud/run_baseline_and_sweep.sh`: fetch W&B/HF secrets
from Secret Manager (`cloud/fetch_secrets.sh`) → baseline
`python -m scipali.models.train` → `wandb sweep configs/sweep.yaml` →
`wandb agent <sweep> --count N` → evaluate the best trial `--by-subject`.

## Evaluate an adapter

```bash
# local
uv run python -m scipali.models.evaluate checkpoints/adapter-production --by-subject
# standalone Vertex eval job against any GCS adapter
TEMPLATE=cloud/vertex_eval.template.yaml RENDERED=cloud/vertex_eval.yaml \
  DISPLAY_NAME=paligemma-eval \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

## Optimize: quantization + pruning

Inference-optimization experiments on an L4 (results feed `reports/RESULTS.md`).
Run on Vertex via `cloud/run_optimize.sh` + `watch_job.sh`:

```bash
# quantization benchmark: bf16 vs int4 (bitsandbytes) vs bf16+torch.compile
TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-optimize \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh

# weight-pruning sweep: accuracy vs sparsity over the full test split
# (SKIP_BENCHMARK=1 runs prune-only; fits a 32GB host via a histogram threshold)
SKIP_BENCHMARK=1 PRUNE_SPARSITIES=0.0,0.3,0.5,0.7 PRUNE_N_BATCHES=0 \
  TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-prune \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

The underlying Typer CLI (CUDA-only; runs inside the L4 container):

```bash
python -m scipali.models.optimize benchmark <adapter_dir> --output-path optimize_results.json
python -m scipali.models.optimize prune-sweep <adapter_dir> \
  --sparsities 0.0,0.3,0.5,0.7 --output-path prune_results.json
```

> A `prune-finetune` command (prune → masked fine-tune to recover accuracy) also
> exists, but it is **explored, not a deliverable**: pruning is an inference-time
> technique, and a short fine-tune recovered only ~1 pt — so we report the
> one-shot accuracy-vs-sparsity curve instead.

> **Build note:** the train/optimize image installs a locally-built wheel, so it
> is built **manually** via `/tmp` staging (a bare `gcloud builds submit` from the
> iCloud working dir stalls). The `mlops-ci-train` trigger is therefore disabled;
> `mlops-ci-api` still builds the API image on push.

## Predict / serve

```bash
# single prediction (also accepts --hint, --lecture, and --max-new-tokens —
# the same optional fields the API's /predict body takes)
uv run python -m scipali.serving.predict checkpoints/adapter-production \
  -q "What gas do plants absorb?" -c "oxygen,carbon dioxide,nitrogen" -i img.png \
  --hint "Plants need sunlight to grow." --lecture "Photosynthesis converts CO2..."

# API (local; PREDICT_DEVICE=cpu since MPS crashes on PaliGemma matmuls)
CHECKPOINT_PATH=checkpoints/adapter-production PREDICT_DEVICE=cpu \
  uv run uvicorn scipali.serving.api:app --port 8000

# Streamlit frontend over the API — launched standalone via uvx (it imports no
# project code, and Streamlit's Starlette server conflicts with FastAPI's
# pinned starlette, so it is kept out of the project env on purpose).
# Two modes: "Ask your own" (type a question) and "Pick from ScienceQA" (browse
# the processed test split by subject/topic and compare to ground truth). The
# dataset picker needs `--with datasets` + the local processed split; "Ask your
# own" works without either.
API_URL=http://localhost:8000 \
  uvx --with streamlit==1.53.0 --with requests --with pillow --with datasets \
  streamlit run src/scipali/serving/frontend.py
```

Point `API_URL` at the deployed Cloud Run URL instead to drive the live service.

There is also a shell demo of the deployed API (health → predict → drift):

```bash
./cloud/demo_api.sh                              # auto-uses test sample 0
./cloud/demo_api.sh img.png "Question?" "a,b,c"  # bring your own sample
```

Under the hood, the demo is three raw calls — the API takes JSON with a
base64-encoded image:

```bash
API=https://paligemma-api-581237630637.europe-west4.run.app
curl "$API/"                       # health — model_loaded flips true after the 1st predict
curl -s -X POST "$API/predict" -H 'Content-Type: application/json' -d '{
  "question": "What is the capital of Wyoming?",
  "choices": ["Phoenix", "Baton Rouge", "Honolulu", "Cheyenne"],
  "image_b64": "'"$(base64 < img.png | tr -d '\n')"'"}'
curl "$API/monitor/drift"          # Evidently drift check vs the seeded reference
curl -s "$API/metrics" | head      # Prometheus metrics
```

## Container images

Three Dockerfiles live in `dockerfiles/`: `train.dockerfile`, `api.dockerfile`,
and `predict.dockerfile`. `train.dockerfile` installs scipali from a
**prebuilt wheel** rather than building it in-image (see the comment in the
Dockerfile), so generate that first:

```bash
uv build --wheel -o wheelhouse
```

Then build all three locally with the Invoke task:

```bash
inv docker-build        # builds train + api + predict images locally (see tasks.py)
```

Pushing to Artifact Registry
(`europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/`) — normally
done by Cloud Build (`gcloud builds submit --config=cloud/cloudbuild.*.yaml .`,
which also builds amd64 remotely); the manual path needs one-time docker auth:

```bash
gcloud auth configure-docker europe-west4-docker.pkg.dev   # once
docker tag api:latest europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-api:latest
docker push europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-api:latest
```

All three were built and smoke-tested locally on 2026-07-05: `api:latest`
serves `GET /` correctly under `LAZY_LOAD=1`; `predict:latest`'s CLI renders
via `--help`; `train:latest` installs CUDA torch (`2.6.0+cu118`) and imports
every `scipali` subpackage cleanly. `train.dockerfile` needs
`--platform=linux/amd64`, so on Apple Silicon it builds under emulation
(slow, ~15 min) — real GPU training still needs a CUDA host, same as Vertex.

The API image is **continuously built and verified in CI**: the Cloud Build
trigger `mlops-ci-api` rebuilds `api.dockerfile` (amd64) on every push to
`main` that touches `src/scipali/**` or the build configs, so a failing
Dockerfile breaks the build. `mlops-ci-train` exists but is **disabled** (see
the build note above — it needs the locally-built wheel injected, which a
bare CI checkout doesn't have), so `train.dockerfile` is built manually. All
three images were also verified with a real local build, per above.

## Deploy to Cloud Run

Build the API image (amd64) and deploy. The service reads its adapter from
`CHECKPOINT_PATH` (a `gs://` path), so promoting a new model needs no redeploy.

```bash
# 1. build + push the API image
gcloud builds submit --config=cloud/cloudbuild.api.yaml --project=paligemma-scienceqa .

# 2. deploy (CPU, scale-to-zero, lazy model load)
# !! NOTE on :latest: the tag was broken on 2026-07-11 (in-image subpackage-drop
# !! bug); an import-guard step in cloudbuild.api.yaml now gates every push
# !! (green since 2026-07-16). The live service stays digest-pinned until the
# !! next deliberate redeploy (same note in the root README) — to reproduce the
# !! live revision exactly, use the digest form:
# !!   --image europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-api@sha256:061ad5202756db5b5965c56f0b6468ba5dc9b6ad286275e768fd1e203b949412
gcloud run deploy paligemma-api \
  --image europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-api:latest \
  --region europe-west4 --project paligemma-scienceqa \
  --execution-environment gen2 \
  --memory 32Gi --cpu 8 \
  --timeout 3600 --concurrency 1 --max-instances 3 --min-instances 0 \
  --set-env-vars CHECKPOINT_PATH=gs://mlops-paligemma-west4/models/production,PREDICT_DEVICE=cpu,LAZY_LOAD=1 \
  --set-secrets HF_TOKEN=hf-token:latest \
  --service-account 581237630637-compute@developer.gserviceaccount.com \
  --allow-unauthenticated
```

Notes: `concurrency 1` keeps one heavy inference per instance (avoids OOM on the
3B model); `max-instances 3` lets overflow requests spin new instances instead
of returning 429. First call to each instance is slow — a direct `/predict` on a
scaled-to-zero instance (container start + model download/load + inference, all
bundled) runs **~150–230 s (typically ~160–175 s)**; once warm, calls run
**~25–80 s (commonly ~35–50 s)**.

## Monitoring & operations

```bash
# data-drift report (Evidently) -> reports/monitoring/drift_report.html
uv run --group serving python -m scipali.monitoring.monitoring drift
# production drift loop: collect real traffic / rebuild the reference
uv run --group serving python -m scipali.monitoring.monitoring collect --project paligemma-scienceqa
uv run --group serving python -m scipali.monitoring.monitoring seed-reference
# load test the deployed API (locust)
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 5 -r 1 -t 1m --host <cloud-run-url>
# BentoML serving
uv run --group serving bentoml serve scipali.serving.bento_service:ScienceQAService
```
