# scipali — Answer Your Science Questions

[![Unit Tests](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/tests.yaml/badge.svg)](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/tests.yaml)
[![Code linting](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/linting.yaml/badge.svg)](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/linting.yaml)
[![codecov](https://codecov.io/gh/yuxinliu42/finetune_paligemma2_scienceqa/graph/badge.svg)](https://codecov.io/gh/yuxinliu42/finetune_paligemma2_scienceqa)

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
in [`reports/figures/architecture.jpg`](reports/figures/architecture.jpg)).

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
behind a FastAPI service on Cloud Run with a Streamlit UI on top (see the
[command guide](#command-guide)).

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

## Command guide

Copy-paste commands for every routine operation. Details and variants live in
[`docs/source/usage.md`](docs/source/usage.md); results they produce are in
[`reports/RESULTS.md`](reports/RESULTS.md).

**Contents**

- **[Setup & data](#zone-setup-data)**
  - [Get the repo](#get-the-repo)
  - [Set up the environment](#set-up-the-environment)
  - [Get the data](#get-the-data)
  - [Recreate the dataset from scratch](#recreate-the-dataset-from-scratch)
  - [Publish a new data version](#publish-a-new-data-version)
  - [Change hyperparameters (Hydra)](#change-hyperparameters-hydra)
- **[Quality & CI](#zone-quality-ci)**
  - [Pre-commit hooks](#pre-commit-hooks)
  - [Run tests and coverage](#run-tests-and-coverage)
  - [Lint and type-check](#lint-and-type-check)
  - [What CI runs on every push](#what-ci-runs-on-every-push)
- **[Docker](#zone-docker)**
  - [Build the docker images](#build-the-docker-images)
  - [Run the API in a docker container](#run-the-api-in-a-docker-container)
- **[Training & evaluation](#zone-training-evaluation)**
  - [Train locally](#train-locally)
  - [Train on Vertex AI](#train-on-vertex-ai)
  - [Evaluate an adapter](#evaluate-an-adapter)
  - [Profile the dataloader](#profile-the-dataloader)
  - [Distributed training](#distributed-training)
- **[Inference optimization](#zone-inference-optimization)**
  - [Quantization and compile benchmark](#quantization-and-compile-benchmark)
  - [Pruning sweep](#pruning-sweep)
- **[Serving & deployment](#zone-serving-deployment)**
  - [Predict on a single sample](#predict-on-a-single-sample)
  - [Serve the API locally](#serve-the-api-locally)
  - [Launch the Streamlit UI](#launch-the-streamlit-ui)
  - [Demo the live API](#demo-the-live-api)
  - [Deploy to Cloud Run](#deploy-to-cloud-run)
  - [Promote a new model to production](#promote-a-new-model-to-production)
- **[Monitoring & ops](#zone-monitoring-ops)**
  - [Data-drift report](#data-drift-report)
  - [Load test](#load-test)
  - [Set up the 5xx alert](#set-up-the-5xx-alert)
  - [Serve the docs site](#serve-the-docs-site)
  - [Regenerate the result figures](#regenerate-the-result-figures)

<a id="zone-setup-data"></a>
### Setup & data [[Back To Contents]](#command-guide)

#### Get the repo

```bash
git clone https://github.com/yuxinliu42/finetune_paligemma2_scienceqa.git
cd finetune_paligemma2_scienceqa
```

#### Set up the environment

```bash
uv sync                      # creates .venv from uv.lock (Python 3.11)
```

Cloud commands additionally need `gcloud auth login`; training/prediction needs
access to the gated PaliGemma2 base model (HF token) and W&B login for tracking.

#### Get the data

```bash
dvc pull                     # fetch the DVC-tracked processed dataset from GCS
# check DVC is working correctly:
dvc doctor                   # env + remote sanity — same check the data-change CI runs
dvc status -c                # is the local cache in sync with the GCS remote?
```

#### Recreate the dataset from scratch

```bash
uv run inv preprocess-data   # = data.data download + data.data preprocess
# or the underlying commands:
uv run python -m scipali.data.data download
uv run python -m scipali.data.data preprocess --overwrite
```

#### Publish a new data version

```bash
dvc push                     # upload the new processed data to the GCS remote
```

Committing the changed `*.dvc` pointer triggers the `data-change` workflow (DVC
sanity check + data tests) on GitHub Actions.

#### Change hyperparameters (Hydra)

Configs are Hydra groups in `configs/` (`data` / `model` / `trainer` / `sweep`);
override any value on the command line:

```bash
uv run train model.base_learning_rate=1.33e-4 trainer.max_epochs=2
```

The effective LR is derived from `model.base_learning_rate` via a sqrt
batch-size rule (`resolve_learning_rate` in `train.py`).

<a id="zone-quality-ci"></a>
### Quality & CI [[Back To Contents]](#command-guide)

#### Pre-commit hooks

```bash
uv run pre-commit install            # install the git hooks (once)
uv run pre-commit run --all-files    # run them on the whole repo
```

Hooks: trailing-whitespace, EOF fixer, YAML check, large-file guard, ruff
(lint + format).

#### Run tests and coverage

```bash
uv run inv test                        # shortcut for the two commands below
uv run coverage run -m pytest tests/   # run the suite under coverage
uv run coverage report -m -i           # per-file coverage table
uv run pytest tests/                   # tests only, no coverage
```

#### Lint and type-check

```bash
uv run ruff check .          # lint (same command CI runs)
uv run ruff format . --check # formatting
uv run mypy .                # static types
```

#### What CI runs on every push

- `tests.yaml` — pytest suite; coverage uploaded to Codecov (badge above).
- `linting.yaml` — ruff check + format + mypy.
- `docs.yaml` — builds and deploys the MkDocs site.
- `data-change.yaml` — on `*.dvc` changes: DVC sanity check + data tests.
- `model-registry-change.yaml` — on a W&B registry webhook
  (`repository_dispatch`): rolls a new Cloud Run revision + smoke test.
- Cloud Build trigger `mlops-ci-api` rebuilds the API image on every push to
  `main` touching `src/scipali/**`. (`mlops-ci-train` is disabled — the train
  image needs a locally-built wheel, so it is built manually.)

<a id="zone-docker"></a>
### Docker [[Back To Contents]](#command-guide)

#### Build the docker images

```bash
uv build --wheel -o wheelhouse   # train image installs this prebuilt wheel
uv run inv docker-build          # builds train + api + predict images
# or the underlying commands:
docker build -t train:latest   . -f dockerfiles/train.dockerfile
docker build -t api:latest     . -f dockerfiles/api.dockerfile
docker build -t predict:latest . -f dockerfiles/predict.dockerfile
```

Platform: `train.dockerfile` is pinned to `linux/amd64` (CUDA wheels), so on
Apple Silicon it builds under emulation (slow, ~15 min); `api` and `predict`
build natively anywhere. The api image built here is exactly what Cloud Run
serves — see [Deploy to Cloud Run](#deploy-to-cloud-run).

The three Dockerfiles live in `dockerfiles/` (`train` / `api` / `predict`).
Testing them: the next entry smoke-tests the API image; the train image gets an
import smoke test without a GPU (this exact check caught a real packaging bug —
see the comment in `train.dockerfile`); and CI rebuilds `api.dockerfile` on
every push (`mlops-ci-api`), so a broken Dockerfile fails CI:

```bash
docker run --rm --platform=linux/amd64 train:latest \
  python -c "import scipali.models.train, scipali.models.optimize"
```

**Note — env for real training runs.** The train container bundles GPU training
(CUDA torch), automatic data preparation (`entrypoint.sh` runs `dvc pull` at
startup), and W&B logging. On Vertex AI all of this is prepared automatically:
W&B/HF keys are fetched from Secret Manager and GCS access comes from the job's
service account. To run it anywhere else, prepare the env yourself — an NVIDIA
GPU (`docker run --gpus all …`), `WANDB_API_KEY`, `HF_TOKEN`, and GCS
credentials for the DVC pull. The single-run path, `entrypoint.sh`, is three
specific commands:

```bash
. cloud/fetch_secrets.sh                                  # W&B/HF keys from Secret Manager
uv run --no-sync dvc pull data/processed/ScienceQA-IMG.dvc
uv run --no-sync train "$@"
```

#### Run the API in a docker container

```bash
docker run -p 8000:8000 -e LAZY_LOAD=1 api:latest
curl localhost:8000/             # health check — serves immediately, model loads lazily
```

Real predictions in the container need `CHECKPOINT_PATH` (e.g. a `gs://` adapter
path) and GCP/HF credentials, as in [Serve the API locally](#serve-the-api-locally).

<a id="zone-training-evaluation"></a>
### Training & evaluation [[Back To Contents]](#command-guide)

#### Train locally

```bash
uv run train trainer.wandb.enabled=true trainer.wandb.run_name=local-test
```

#### Train on Vertex AI

The cloud-training path: submits a Vertex AI custom job on a single L4 GPU
(`europe-west4`, Flex Start queue) running the train image — data arrives via
the automatic `dvc pull`, W&B/HF secrets via Secret Manager (see the Docker note).

```bash
bash cloud/watch_job.sh                  # baseline + W&B sweep + eval, on one L4
SKIP_BASELINE=1 bash cloud/watch_job.sh  # sweep only
```

Under the hood (the explicit method, simplified — the script adds retries,
image digest-pinning, and log streaming): render the job spec from its
template, submit it, watch the logs.

```bash
envsubst < cloud/vertex_config.template.yaml > cloud/vertex_config.yaml
gcloud ai custom-jobs create --region=europe-west4 --project=paligemma-scienceqa \
  --display-name=paligemma-train --config=cloud/vertex_config.yaml
gcloud ai custom-jobs stream-logs <job-id> --region=europe-west4
```

Inside the container, the job spec runs `bash cloud/run_baseline_and_sweep.sh`,
whose specific steps are:

```bash
. cloud/fetch_secrets.sh    # W&B/HF keys from Secret Manager (google-auth REST;
                            # manual equivalent: gcloud secrets versions access latest --secret=wandb-api-key)
python -c "import torch; assert torch.cuda.is_available()"          # fail fast on a bad image
python -m scipali.models.train trainer.wandb.enabled=true trainer.wandb.run_name=baseline
wandb sweep --project "$WANDB_PROJECT" configs/sweep.yaml           # register the Bayesian sweep
wandb agent <entity/project/sweep-id> --count "$SWEEP_COUNT"        # run N trials
python -m scipali.models.evaluate <best-adapter> --by-subject      # test the best trial
```

Picking the GPU: accelerators are not available in every region — this is how
you discover where one exists (for us, L4/G2 capacity meant `europe-west4`):

```bash
gcloud compute accelerator-types list --filter="name=nvidia-l4"
```

The fully manual alternative — `gcloud compute instances create <name>
--zone=… --accelerator=type=nvidia-l4,count=1 …` — spins up a raw GPU VM you
must SSH into, run, and remember to delete. We deliberately use managed Vertex
custom jobs instead: the machine exists only for the job's lifetime, and the
image, DVC data pull, and secrets are wired in automatically.

#### Evaluate an adapter

```bash
# local
uv run python -m scipali.models.evaluate checkpoints/adapter-production --by-subject
# standalone Vertex eval job against any GCS adapter
TEMPLATE=cloud/vertex_eval.template.yaml RENDERED=cloud/vertex_eval.yaml \
  DISPLAY_NAME=paligemma-eval \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

The Vertex variant is the same explicit method as
[Train on Vertex AI](#train-on-vertex-ai), just rendering
`cloud/vertex_eval.template.yaml` instead — as are the two optimization jobs
below (`cloud/vertex_optimize.template.yaml`). Inside the container the eval
job runs `cloud/run_eval.sh`: download the adapter from GCS, then the same
`python -m scipali.models.evaluate <adapter> --by-subject` as above, then
upload the results JSON.

#### Profile the dataloader

```bash
uv run python -m scipali.data.profile_data --workers 0,2,4
```

cProfile + per-worker-count timings; results in `reports/profiling/`.


<a id="zone-inference-optimization"></a>
### Inference optimization [[Back To Contents]](#command-guide)

#### Quantization and compile benchmark

```bash
# bf16 vs int4 (bitsandbytes) vs bf16+torch.compile, on an L4
TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-optimize \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

Inside the container, `cloud/run_optimize.sh` runs the underlying CLI:

```bash
python -m scipali.models.optimize benchmark <adapter_dir> --output-path optimize_results.json
```

#### Pruning sweep

```bash
# accuracy vs sparsity over the full test split (prune-only, fits a 32GB host)
SKIP_BENCHMARK=1 PRUNE_SPARSITIES=0.0,0.3,0.5,0.7 PRUNE_N_BATCHES=0 \
  TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-prune \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

Inside the container, `cloud/run_optimize.sh` runs the underlying CLI:

```bash
python -m scipali.models.optimize prune-sweep <adapter_dir> \
  --sparsities 0.0,0.3,0.5,0.7 --output-path prune_results.json
```

A `prune-finetune` command (masked fine-tune to recover accuracy) also exists —
see the note in [`docs/source/usage.md`](docs/source/usage.md#optimize-quantization--pruning).

<a id="zone-serving-deployment"></a>
### Serving & deployment [[Back To Contents]](#command-guide)

#### Predict on a single sample

```bash
uv run python -m scipali.serving.predict checkpoints/adapter-production \
  -q "What gas do plants absorb?" -c "oxygen,carbon dioxide,nitrogen" -i img.png
```

Also accepts `--hint`, `--lecture`, `--max-new-tokens` — the same optional
fields as the API's `/predict` body. On a Mac, prefix `PREDICT_DEVICE=cpu`
(MPS crashes on PaliGemma matmuls); add `HF_HUB_OFFLINE=1` to load the gated
base model from the local HF cache when no HF token is configured.

#### Serve the API locally

The FastAPI service (`src/scipali/serving/api.py`) serves single-sample
ScienceQA predictions. `CHECKPOINT_PATH` accepts a local adapter dir, a `.ckpt`
file, or a `gs://` directory — the stable production path is fetched at
startup, so a promoted adapter needs **no rebuild or redeploy**:

```bash
CHECKPOINT_PATH=checkpoints/adapter-production PREDICT_DEVICE=cpu \
  uv run uvicorn scipali.serving.api:app --port 8000
# or serve the deployed production adapter straight from GCS:
CHECKPOINT_PATH=gs://mlops-paligemma-west4/models/production PREDICT_DEVICE=cpu \
  uv run uvicorn scipali.serving.api:app --port 8000
# BentoML alternative:
uv run --group serving bentoml serve scipali.serving.bento_service:ScienceQAService
```

#### Launch the Streamlit UI

```bash
API_URL=http://localhost:8000 \
  uvx --with streamlit==1.53.0 --with requests --with pillow --with datasets \
  streamlit run src/scipali/serving/frontend.py
```

Two modes: "Ask your own" (type a free question) and "Pick from ScienceQA"
(browse the processed test split and compare against ground truth). Point
`API_URL` at the live service instead to drive the deployed model:
`https://paligemma-api-581237630637.europe-west4.run.app`.

#### Demo the live API

```bash
./cloud/demo_api.sh                              # health → predict → drift, test sample 0
./cloud/demo_api.sh img.png "Question?" "a,b,c"  # bring your own sample
```

The first call on a scaled-to-zero instance takes ~2–4 min while the container
starts and the model loads.

Under the hood — the three raw calls (the API takes JSON with a
base64-encoded image):

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

#### Deploy to Cloud Run

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

The service is CPU-only (8 vCPU / 32 GB), `min-instances 0` (scale-to-zero)
with lazy model loading — an always-on GPU endpoint would cost more than a
course project justifies. Cold `/predict` runs ~150–230 s (container start +
model load + inference); warm calls ~25–80 s. Full latency breakdown in
[`docs/source/api.md`](docs/source/api.md); flag rationale in
[`docs/source/usage.md`](docs/source/usage.md#deploy-to-cloud-run).

#### Promote a new model to production

```bash
gcloud storage cp -r <new-adapter-dir> gs://mlops-paligemma-west4/models/production
```

Then move the W&B `production` alias to the new version (W&B UI). The registry
webhook fires the `model-registry-change` workflow, which rolls out a fresh
Cloud Run revision and smoke-tests it — **no image rebuild needed**.

<a id="zone-monitoring-ops"></a>
### Monitoring & ops [[Back To Contents]](#command-guide)

#### Data-drift report

```bash
uv run --group serving python -m scipali.monitoring.monitoring   # Evidently report
```

The live service also exposes `/monitor/drift` (drift vs a seeded reference)
and Prometheus metrics at `/metrics`.

#### Load test

```bash
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 5 -r 1 -t 1m --host <cloud-run-url>
```

#### Set up the 5xx alert

```bash
uv run python cloud/setup_monitoring.py   # idempotent: email channel + 5xx alert policy
```

Fires on any 5xx from the API within 5 minutes → email. View under GCP
Monitoring → Alerting.

#### Serve the docs site

```bash
uv run inv serve-docs        # live-reload at localhost:8000
uv run inv build-docs        # static build (CI deploys via docs.yaml)
```

#### Regenerate the result figures

```bash
uv run python -m scipali.models.visualize prune-curve reports/eval/prune_results.json
uv run python -m scipali.models.visualize subject-accuracy reports/eval/production_eval_results.json
```

Full list of figure commands in
[`reports/RESULTS.md`](reports/RESULTS.md#figures-reportsfigures).

---

Created using [mlops_template](https://github.com/SkafteNicki/mlops_template), a
[cookiecutter template](https://github.com/cookiecutter/cookiecutter) for MLOps.
