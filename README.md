# scipali — Answer Your Science Questions

[![Unit Tests](https://github.com/yuxinliu42/SS26_MLOps_Project_GroupA/actions/workflows/tests.yaml/badge.svg)](https://github.com/yuxinliu42/SS26_MLOps_Project_GroupA/actions/workflows/tests.yaml)
[![Code linting](https://github.com/yuxinliu42/SS26_MLOps_Project_GroupA/actions/workflows/linting.yaml/badge.svg)](https://github.com/yuxinliu42/SS26_MLOps_Project_GroupA/actions/workflows/linting.yaml)
[![codecov](https://codecov.io/gh/yuxinliu42/SS26_MLOps_Project_GroupA/graph/badge.svg)](https://codecov.io/gh/yuxinliu42/SS26_MLOps_Project_GroupA)

<p align="center">
  <img src="reports/figures/science-qa.jpg" alt="Science banner" width="720">
</p>

PaliGemma2-3B fine-tuned (LoRA) on ScienceQA-IMG, wrapped in a full MLOps
pipeline — DVC data versioning, Hydra configs, W&B sweeps, Vertex AI training,
Cloud Run serving, drift monitoring, and CI/CD. Headline: **72.19%** exact-match
accuracy on the 2,017-sample test split. Full results in
[`reports/RESULTS.md`](reports/RESULTS.md); usage in
[`docs/source/usage.md`](docs/source/usage.md).

## Project description

### Goal
The project has two goals: **improve the reasoning accuracy** of the pretrained
PaliGemma foundation model on multimodal science questions, and do it inside a
**complete, reproducible MLOps pipeline** — versioned data, configurable
training, tracked experiments, automated deployment, and monitoring (diagrammed
in [`reports/figures/architecture.png`](reports/figures/architecture.png)).

### Framework
The Hugging Face **Transformers** framework. We build on its main strength —
thousands of pretrained models — by starting from a pretrained PaliGemma2
checkpoint and fine-tuning it on our data rather than training anything from
scratch. Around it: **PEFT/LoRA** for parameter-efficient fine-tuning,
**PyTorch Lightning** for the training loop, and **Hydra** for configuration
management.

### Use case & target users
Given a science question, a supporting image, and a set of answer choices, the
model picks the correct answer. The natural users are students and educational
tools (ScienceQA is grade-school science material); within this course the
served model is above all the workload that exercises the pipeline — deployed
behind a FastAPI service on Cloud Run with a Streamlit UI on top (see
[Serving](#serving)).

### Dataset
**[`derek-thomas/ScienceQA`](https://huggingface.co/datasets/derek-thomas/ScienceQA)**,
the image subset ("ScienceQA-IMG"): train 6,218 / val 2,097 / test 2,017. Each
sample has an image, a question, answer choices, the answer index, and optional
hint / lecture plus a subject label. (We initially planned `lmms-lab/ScienceQA`,
but that mirror ships no train split, so we switched.)

### Model
The **PaliGemma2-3B** vision-language model
([`google/paligemma2-3b-pt-224`](https://huggingface.co/google/paligemma2-3b-pt-224)),
LoRA-adapted on the language-model attention projections (`q/k/v/o_proj`) with
the vision encoder frozen — ~6.4 M trainable parameters against ~3 B frozen.

## Project structure

```txt
├── .github/workflows/      # CI: tests, linting, docs, data-change, model-registry
├── cloud/                  # Vertex AI + Cloud Build + ops scripts
├── configs/                # Hydra configs (data / model / trainer / sweep)
├── data/                   # DVC-tracked dataset (git-tracked pointers; data on GCS)
├── dockerfiles/            # api / train / predict images
├── docs/                   # MkDocs site
├── reports/                # figures, eval, profiling, monitoring, load + RESULTS.md
├── src/scipali/
│   ├── data/               # data.py, profile_data.py
│   ├── models/             # model.py, train.py, evaluate.py, optimize.py, visualize.py
│   ├── serving/            # api.py, predict.py, frontend.py, bento_service.py
│   └── monitoring/         # monitoring.py
├── tests/                  # pytest suite
├── pyproject.toml
└── tasks.py                # invoke tasks
```

## How do I …? (command guide)

Copy-paste commands for every routine operation. Details and variants live in
[`docs/source/usage.md`](docs/source/usage.md); results they produce are in
[`reports/RESULTS.md`](reports/RESULTS.md).

**Setup & data** ·
[Set up the environment](#set-up-the-environment) ·
[Get the data](#get-the-data) ·
[Recreate the dataset from scratch](#recreate-the-dataset-from-scratch) ·
[Publish a new data version](#publish-a-new-data-version) ·
[Change hyperparameters](#change-hyperparameters)

**Quality & CI** ·
[Pre-commit hooks](#pre-commit-hooks) ·
[Run tests and coverage](#run-tests-and-coverage) ·
[Lint and type-check](#lint-and-type-check) ·
[What CI runs on every push](#what-ci-runs-on-every-push)

**Docker** ·
[Build the docker images](#build-the-docker-images) ·
[Run the API in a docker container](#run-the-api-in-a-docker-container)

**Training & evaluation** ·
[Train locally](#train-locally) ·
[Train on Vertex AI](#train-on-vertex-ai) ·
[Evaluate an adapter](#evaluate-an-adapter) ·
[Profile the dataloader](#profile-the-dataloader) ·
[Distributed training](#distributed-training)

**Inference optimization** ·
[Quantization and compile benchmark](#quantization-and-compile-benchmark) ·
[Pruning sweep](#pruning-sweep)

**Serving & deployment** ·
[Predict on a single sample](#predict-on-a-single-sample) ·
[Serve the API locally](#serve-the-api-locally) ·
[Launch the Streamlit UI](#launch-the-streamlit-ui) ·
[Demo the live API](#demo-the-live-api) ·
[Deploy to Cloud Run](#deploy-to-cloud-run) ·
[Promote a new model to production](#promote-a-new-model-to-production)

**Monitoring & ops** ·
[Data-drift report](#data-drift-report) ·
[Load test](#load-test) ·
[Set up the 5xx alert](#set-up-the-5xx-alert) ·
[Serve the docs site](#serve-the-docs-site) ·
[Regenerate the result figures](#regenerate-the-result-figures)

### Set up the environment

```bash
uv sync                      # creates .venv from uv.lock (Python 3.11)
```

Cloud commands additionally need `gcloud auth login`; training/prediction needs
access to the gated PaliGemma2 base model (HF token) and W&B login for tracking.

### Get the data

```bash
dvc pull                     # fetch the DVC-tracked processed dataset from GCS
```

### Recreate the dataset from scratch

```bash
uv run inv preprocess-data   # = data.data download + data.data preprocess
# or the underlying commands:
uv run python -m scipali.data.data download
uv run python -m scipali.data.data preprocess --overwrite
```

### Publish a new data version

```bash
dvc push                     # upload the new processed data to the GCS remote
```

Committing the changed `*.dvc` pointer triggers the `data-change` workflow (DVC
sanity check + data tests) on GitHub Actions.

### Change hyperparameters

Configs are Hydra groups in `configs/` (`data` / `model` / `trainer` / `sweep`);
override any value on the command line:

```bash
uv run train model.base_learning_rate=1.33e-4 trainer.max_epochs=2
```

The effective LR is derived from `model.base_learning_rate` via a sqrt
batch-size rule (`resolve_learning_rate` in `train.py`).

### Pre-commit hooks

```bash
uv run pre-commit install            # install the git hooks (once)
uv run pre-commit run --all-files    # run them on the whole repo
```

Hooks: trailing-whitespace, EOF fixer, YAML check, large-file guard, ruff
(lint + format).

### Run tests and coverage

```bash
uv run inv test              # = coverage run -m pytest tests/ + coverage report
uv run pytest tests/         # tests only
```

### Lint and type-check

```bash
uv run ruff check .          # lint (same command CI runs)
uv run ruff format . --check # formatting
uv run mypy .                # static types
```

### What CI runs on every push

- `tests.yaml` — pytest suite; coverage uploaded to Codecov (badge above).
- `linting.yaml` — ruff check + format + mypy.
- `docs.yaml` — builds and deploys the MkDocs site.
- `data-change.yaml` — on `*.dvc` changes: DVC sanity check + data tests.
- `model-registry-change.yaml` — on a W&B registry webhook
  (`repository_dispatch`): rolls a new Cloud Run revision + smoke test.
- Cloud Build trigger `mlops-ci-api` rebuilds the API image on every push to
  `main` touching `src/scipali/**`. (`mlops-ci-train` is disabled — the train
  image needs a locally-built wheel, so it is built manually.)

### Build the docker images

```bash
uv build --wheel -o wheelhouse   # train image installs this prebuilt wheel
uv run inv docker-build          # builds train + api + predict images
```

### Run the API in a docker container

```bash
docker run -p 8000:8000 -e LAZY_LOAD=1 api:latest
curl localhost:8000/             # health check — serves immediately, model loads lazily
```

Real predictions in the container need `CHECKPOINT_PATH` (e.g. a `gs://` adapter
path) and GCP/HF credentials, as in [Serving](#serving).

### Train locally

```bash
uv run train trainer.wandb.enabled=true trainer.wandb.run_name=local-test
```

### Train on Vertex AI

```bash
bash cloud/watch_job.sh                  # baseline + W&B sweep + eval, on one L4
SKIP_BASELINE=1 bash cloud/watch_job.sh  # sweep only
```

### Evaluate an adapter

```bash
# local
uv run python -m scipali.models.evaluate checkpoints/adapter-production --by-subject
# standalone Vertex eval job against any GCS adapter
TEMPLATE=cloud/vertex_eval.template.yaml RENDERED=cloud/vertex_eval.yaml \
  DISPLAY_NAME=paligemma-eval \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

### Profile the dataloader

```bash
uv run python -m scipali.data.profile_data --workers 0,2,4
```

cProfile + per-worker-count timings; results in `reports/profiling/`.

### Distributed training

Not applicable by design — LoRA on a 3B model trains on a **single L4**;
Lightning would enable it via `Trainer(devices=…, strategy="ddp")` if more GPUs
were available. Justification and the data-loading profiling that backs it:
[`reports/RESULTS.md`](reports/RESULTS.md#distributed-training--data-loading).

### Quantization and compile benchmark

```bash
# bf16 vs int4 (bitsandbytes) vs bf16+torch.compile, on an L4
TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-optimize \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

### Pruning sweep

```bash
# accuracy vs sparsity over the full test split (prune-only, fits a 32GB host)
SKIP_BENCHMARK=1 PRUNE_SPARSITIES=0.0,0.3,0.5,0.7 PRUNE_N_BATCHES=0 \
  TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-prune \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

A `prune-finetune` command (masked fine-tune to recover accuracy) also exists —
see the note in [`docs/source/usage.md`](docs/source/usage.md#optimize-quantization--pruning).

### Predict on a single sample

```bash
uv run python -m scipali.serving.predict checkpoints/adapter-production \
  -q "What gas do plants absorb?" -c "oxygen,carbon dioxide,nitrogen" -i img.png
```

Also accepts `--hint`, `--lecture`, `--max-new-tokens` — the same optional
fields as the API's `/predict` body.

### Serve the API locally

```bash
CHECKPOINT_PATH=checkpoints/adapter-production PREDICT_DEVICE=cpu \
  uv run uvicorn scipali.serving.api:app --port 8000
# BentoML alternative:
uv run --group serving bentoml serve scipali.serving.bento_service:ScienceQAService
```

### Launch the Streamlit UI

```bash
API_URL=http://localhost:8000 \
  uvx --with streamlit==1.53.0 --with requests --with pillow --with datasets \
  streamlit run src/scipali/serving/frontend.py
```

Point `API_URL` at the Cloud Run URL to drive the live service (see
[Serving](#serving)).

### Demo the live API

```bash
./cloud/demo_api.sh                              # health → predict → drift, test sample 0
./cloud/demo_api.sh img.png "Question?" "a,b,c"  # bring your own sample
```

### Deploy to Cloud Run

```bash
# 1. build + push the API image
gcloud builds submit --config=cloud/cloudbuild.api.yaml --project=paligemma-scienceqa .

# 2. deploy (CPU, scale-to-zero, lazy model load)
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

Flag rationale in [`docs/source/usage.md`](docs/source/usage.md#deploy-to-cloud-run).

### Promote a new model to production

```bash
gcloud storage cp -r <new-adapter-dir> gs://mlops-paligemma-west4/models/production
```

Then move the W&B `production` alias to the new version (W&B UI). The registry
webhook fires the `model-registry-change` workflow, which rolls out a fresh
Cloud Run revision and smoke-tests it — **no image rebuild needed**.

### Data-drift report

```bash
uv run --group serving python -m scipali.monitoring.monitoring   # Evidently report
```

The live service also exposes `/monitor/drift` (drift vs a seeded reference)
and Prometheus metrics at `/metrics`.

### Load test

```bash
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 5 -r 1 -t 1m --host <cloud-run-url>
```

### Set up the 5xx alert

```bash
uv run python cloud/setup_monitoring.py   # idempotent: email channel + 5xx alert policy
```

Fires on any 5xx from the API within 5 minutes → email. View under GCP
Monitoring → Alerting.

### Serve the docs site

```bash
uv run inv serve-docs        # live-reload at localhost:8000
uv run inv build-docs        # static build (CI deploys via docs.yaml)
```

### Regenerate the result figures

```bash
uv run python -m scipali.models.visualize prune-curve reports/eval/prune_results.json
uv run python -m scipali.models.visualize subject-accuracy reports/eval/production_eval_results.json
```

Full list of figure commands in
[`reports/RESULTS.md`](reports/RESULTS.md#figures-reportsfigures).

## Serving

The FastAPI service (`src/scipali/serving/api.py`, image: `dockerfiles/api.dockerfile`)
serves single-sample ScienceQA predictions from the **production adapter**.

`CHECKPOINT_PATH` accepts a local adapter dir, a `.ckpt` file, or a `gs://` directory —
the stable production path is fetched at startup, so promoting a new adapter
(copy to GCS + W&B `production` alias) requires **no rebuild or redeploy**:

```bash
# local (model weights cached from HF; needs HF access for the gated base model)
CHECKPOINT_PATH=gs://mlops-paligemma-west4/models/production \
  uvicorn scipali.serving.api:app --host 0.0.0.0 --port 8000
```

### Try a prediction

Two demo paths — a terminal script and a browser UI (full details in
[`docs/source/usage.md`](docs/source/usage.md#predict--serve)):

```bash
# terminal: health → predict → drift against the live Cloud Run service
# (first call on a scaled-to-zero instance takes ~2–4 min while the model loads)
./cloud/demo_api.sh                                        # auto-uses test sample 0
./cloud/demo_api.sh img.png "Your question?" "choice a,choice b,choice c"

# browser UI: Streamlit frontend over the same API — "Ask your own" mode types a
# free question; "Pick from ScienceQA" browses the local processed test split
# and compares the prediction to ground truth
API_URL=https://paligemma-api-581237630637.europe-west4.run.app \
  uvx --with streamlit==1.53.0 --with requests --with pillow --with datasets \
  streamlit run src/scipali/serving/frontend.py
```

**Deployment.** The API is deployed to **Cloud Run** (`paligemma-api`,
`europe-west4`): CPU-only (8 vCPU / 32 GB), `min-instances 0` / `max-instances 3`
(scale-to-zero when idle), with lazy model loading — the container passes its
startup probe immediately and only loads the model on the first `/predict`.
Rationale for CPU over an always-on GPU endpoint: PaliGemma2-3B needs a GPU for
interactive latency, but an always-on L4 endpoint (Vertex endpoint or Cloud Run
w/ GPU) costs more than this course project justifies. In practice this means a
direct `/predict` on a cold (scaled-to-zero) instance takes ~150–230s (container
start + model load + inference bundled), while warm calls run ~25–80s — see
[`docs/source/api.md`](docs/source/api.md) for the full latency breakdown.
Promoting a new adapter needs **no image rebuild**: copy it to
`gs://…/models/production` and move the W&B `production` alias — the
model-registry-change workflow then rolls out a fresh Cloud Run revision and
smoke-tests the live endpoint automatically. The full deploy command (memory,
concurrency, and secret flags) lives in
[`docs/source/usage.md`](docs/source/usage.md#deploy-to-cloud-run).

---

Created using [mlops_template](https://github.com/SkafteNicki/mlops_template), a
[cookiecutter template](https://github.com/cookiecutter/cookiecutter) for MLOps.
