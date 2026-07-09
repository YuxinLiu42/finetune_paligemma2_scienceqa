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
  - [Contribute a change](#contribute-a-change)
  - [Pre-commit hooks](#pre-commit-hooks)
  - [Run tests and coverage](#run-tests-and-coverage)
  - [Lint and type-check](#lint-and-type-check)
  - [What CI runs on every push](#what-ci-runs-on-every-push)
- **[Docker](#zone-docker)**
  - [Build the docker images](#build-the-docker-images)
  - [Push the images to Artifact Registry](#push-the-images-to-artifact-registry)
  - [Run the API in a docker container](#run-the-api-in-a-docker-container)
  - [Clean up docker resources](#clean-up-docker-resources)
- **[Training & evaluation](#zone-training-evaluation)**
  - [Train locally](#train-locally)
  - [Run training in a docker container](#run-training-in-a-docker-container)
  - [Train on Vertex AI](#train-on-vertex-ai)
  - [Hyperparameter sweep (W&B)](#hyperparameter-sweep-wb)
  - [Debug a failing cloud job](#debug-a-failing-cloud-job)
  - [Evaluate an adapter](#evaluate-an-adapter)
  - [Profile the dataloader](#profile-the-dataloader)
  - [Distributed training, data, and model](#distributed-training-data-and-model)
- **[Inference optimization](#zone-inference-optimization)**
  - [Quantization and compile benchmark](#quantization-and-compile-benchmark)
  - [Pruning sweep](#pruning-sweep)
- **[Serving & deployment](#zone-serving-deployment)**
  - [Predict on a single sample](#predict-on-a-single-sample)
  - [Serve the API locally](#serve-the-api-locally)
  - [Launch the Streamlit UI](#launch-the-streamlit-ui)
  - [Demo the live API](#demo-the-live-api)
  - [Interpret prediction failures](#interpret-prediction-failures)
  - [Deploy to Cloud Run](#deploy-to-cloud-run)
  - [Promote a new model to production](#promote-a-new-model-to-production)
- **[Monitoring & operations](#zone-monitoring-ops)**
  - [Data-drift report](#data-drift-report)
  - [Load test](#load-test)
  - [Set up the 5xx alert](#set-up-the-5xx-alert)
  - [Serve the docs site](#serve-the-docs-site)
  - [Regenerate the result figures](#regenerate-the-result-figures)
  - [GCP billing: check, recover, rescue](#gcp-billing-check-recover-rescue)
  - [Delete everything](#delete-everything)

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

#### Contribute a change

```bash
git pull origin main            # start from the newest main
uv sync                         # re-sync in case the lockfile moved
uv run pre-commit install       # once per clone — hooks then run on every commit
git checkout -b feat/<name>     # work on a branch, never on main
# ...edit, commit...
uv run pytest tests/            # green before pushing
git push -u origin feat/<name>  # then open a pull request
```

`main` is wired to CI **and** deployment (a push rebuilds the API image), so
changes merge via pull request once CI is green — a broken `main` has real
consequences beyond review.

#### Pre-commit hooks

```bash
uv run pre-commit install            # install the git hooks (once)
uv run pre-commit run --all-files    # run them on the whole repo
uv run pre-commit run --files <file> # check only the files you touched
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

Adding a test: drop `tests/test_<topic>.py` with `test_*` functions — pytest
discovers it automatically. Keep it CPU-fast; GPU-only code paths are guarded
by `mypy` and real cloud runs instead.

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
credentials for the DVC pull. If `--gpus all` errors, the host is missing a
working NVIDIA driver or the NVIDIA Container Toolkit — `nvidia-smi` must
succeed on the host first, then
`docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi`
verifies Docker can see the GPU. (On macOS `--gpus all` can never work — our
GPU containers run on Vertex instead.) The single-run path, `entrypoint.sh`, is three
specific commands:

```bash
. cloud/fetch_secrets.sh                                  # W&B/HF keys from Secret Manager
uv run --no-sync dvc pull data/processed/ScienceQA-IMG.dvc
uv run --no-sync train "$@"
```

#### Push the images to Artifact Registry

Cloud workloads pull images from Artifact Registry
(`europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/`). The API
image (`paligemma-api`) is built and pushed automatically by CI on every push;
the train image (`paligemma-train`) is built and pushed manually via Cloud
Build — it installs the locally-built wheel, which a bare CI checkout doesn't
have (that is why the `mlops-ci-train` trigger is deliberately disabled):

```bash
uv build --wheel -o wheelhouse   # the wheel the train image installs
gcloud builds submit --config=cloud/cloudbuild.train.yaml --project=paligemma-scienceqa .
gcloud builds submit --config=cloud/cloudbuild.api.yaml --project=paligemma-scienceqa .  # manual API build (CI normally does this)
```

One-time auth prerequisites, and the manual `docker push` alternative to
Cloud Build:

```bash
gcloud auth login
gcloud config set project paligemma-scienceqa
gcloud auth configure-docker europe-west4-docker.pkg.dev   # once — lets docker push to AR
docker build --platform=linux/amd64 -t api:latest . -f dockerfiles/api.dockerfile
docker tag api:latest europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-api:latest
docker push europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-api:latest
```

We normally push via Cloud Build instead: it builds amd64 remotely (a plain
local build on Apple Silicon is arm64, which Cloud Run cannot run) and needs
no docker credential setup.

The Vertex job spec (`cloud/vertex_config.template.yaml`) then references this
image and defines the *infrastructure* — machine type, GPU, env vars, image
URI — while the *hyperparameters* live in the Hydra configs: two deliberately
separate configuration layers.

#### Run the API in a docker container

```bash
docker run -p 8000:8000 -e LAZY_LOAD=1 api:latest
curl localhost:8000/             # health check — serves immediately, model loads lazily
```

Real predictions in the container need `CHECKPOINT_PATH` (e.g. a `gs://` adapter
path) and GCP/HF credentials, as in [Serve the API locally](#serve-the-api-locally).

#### Clean up docker resources

The images are large (the train image ships CUDA torch), and test runs without
`--rm` leave stopped containers behind:

```bash
docker ps -a                    # stopped containers left by test runs
docker rm <container-id>        # remove one (or: docker container prune)
docker images                   # list images + sizes
docker rmi <image-id-or-tag>    # e.g. docker rmi train:latest
docker system prune             # dangling layers + build cache
```

<a id="zone-training-evaluation"></a>
### Training & evaluation [[Back To Contents]](#command-guide)

#### Train locally

This runs the **PyTorch Lightning** training loop (`train.py`: `Trainer` with
gradient checkpointing, `ModelCheckpoint` + `EarlyStopping` on `val/accuracy`,
and the end-of-training test pass), configured by Hydra:

```bash
uv run train trainer.wandb.enabled=true trainer.wandb.run_name=local-test
# smoke run — Lightning's fast_dev_run: 1 train + 1 val batch, then exit:
uv run train trainer.fast_dev_run=true trainer.wandb.enabled=false
```

#### Run training in a docker container

This is exactly what the Vertex job does (next entry): it runs the
`paligemma-train` image with `bash cloud/run_baseline_and_sweep.sh` on an L4
— containerized training on a managed GPU host, with data, secrets, and image
wired in automatically. Locally we can only smoke-test the container (no
NVIDIA GPU on macOS — see the Docker zone); on a Linux box with a GPU, the
manual equivalent has this shape (untested here, since Vertex *is* our GPU
host):

```bash
docker run --rm --gpus all -e WANDB_API_KEY -e HF_TOKEN \
  europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-train:latest \
  bash cloud/run_baseline_and_sweep.sh
```

#### Train on Vertex AI

We chose Vertex AI because we have no local GPU and wanted training to be a
managed, ephemeral job rather than a machine: we pay only while the job
runs, there is nothing to SSH into or remember to delete, scarce L4 capacity
is handled by a queue instead of by us, and the image/data/secrets are wired
in automatically. The cloud-training path: submits a Vertex AI custom job on a single L4 GPU
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
# (no id at hand? the $JOB resolver in "Debug a failing cloud job" grabs the newest)
```

Inside the container, the job spec runs `bash cloud/run_baseline_and_sweep.sh`,
whose specific steps are:

```bash
. cloud/fetch_secrets.sh    # W&B/HF keys from Secret Manager (google-auth REST;
                            # manual equivalent: gcloud secrets versions access latest --secret=wandb-api-key)
python -c "import torch; assert torch.cuda.is_available()"
# -> on the L4: "CUDA OK: 11.8" | on a laptop: AssertionError — by design, fail fast
python -m scipali.models.train trainer.wandb.enabled=true trainer.wandb.run_name=baseline
# (the same run locally: uv run train trainer.wandb.enabled=true trainer.wandb.run_name=baseline)
wandb sweep --project scienceqa-paligemma2 configs/sweep.yaml       # register the Bayesian sweep
# -> wandb: Created sweep with ID: <id>
# -> wandb: Run sweep agent with: wandb agent <entity>/scienceqa-paligemma2/<id>
wandb agent <entity>/scienceqa-paligemma2/<id> --count 8            # paste the printed string;
                                                                    # 8 = the SWEEP_COUNT default
python -m scipali.models.evaluate checkpoints/adapter-production --by-subject   # test an adapter
```

All the `$VARS` above are documented, with defaults, in the header of
`cloud/run_baseline_and_sweep.sh` (`WANDB_PROJECT=scienceqa-paligemma2`,
`SWEEP_COUNT=8`, …) — grep the script when in doubt.

Checking the job and its GPU — there is nothing to SSH into: Vertex workers
are managed machines that exist only for the job's lifetime, so the windows in
are `describe` and the log stream:

```bash
gcloud ai custom-jobs list --region=europe-west4 --project=paligemma-scienceqa   # our "instances": jobs
gcloud ai custom-jobs describe <job-id> --region=europe-west4 \
  --format="yaml(state, jobSpec.workerPoolSpecs[0].machineSpec)"   # machine + accelerator actually granted
gcloud compute instances list                                      # empty by design — no long-lived VMs
```

The GPU-is-linked check is the fail-fast CUDA assert at the top of the job
(above): a CPU-only or driverless container dies in seconds instead of after a
long queue. No image install step exists anywhere — the job spec pins the
Artifact Registry image by digest and Vertex pulls it. And when compute is
scarce there is no error at submit time: the job sits in `JOB_STATE_PENDING`
in the Flex Start queue (we have waited 8 minutes to 16+ hours for an L4) and
only fails if `maxWaitDuration` expires before capacity frees up.

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

#### Hyperparameter sweep (W&B)

The sweep definition is `configs/sweep.yaml` — Bayesian search over
`model.base_learning_rate` (log-uniform) and
`trainer.accumulate_grad_batches`, optimizing generation-based `val/accuracy`
(max), *not* `val/loss` — the two disagree on this task (see
[`reports/RESULTS.md`](reports/RESULTS.md)). Sweeps run inside the Vertex job:

```bash
SKIP_BASELINE=1 bash cloud/watch_job.sh    # submit a sweep-only Vertex job
# inside the job, the two W&B commands (script defaults:
# WANDB_PROJECT=scienceqa-paligemma2, SWEEP_COUNT=8):
wandb sweep --project scienceqa-paligemma2 configs/sweep.yaml
# -> wandb: Created sweep with ID: win9arpw
# -> wandb: Run sweep agent with: wandb agent <entity>/scienceqa-paligemma2/win9arpw
wandb agent <entity>/scienceqa-paligemma2/win9arpw --count 8   # paste the exact
#   agent string from the `wandb sweep` output above — it prints it ready to run
```

Each agent trial launches `train` with sweep-chosen overrides; the best trial
by `val/accuracy` is then test-evaluated `--by-subject`.

#### Debug a failing cloud job

```bash
# resolve the newest job into $JOB — runnable any time, no id to look up:
JOB=$(gcloud ai custom-jobs list --region=europe-west4 --project=paligemma-scienceqa \
  --sort-by=~createTime --limit=1 --format="value(name)")
gcloud ai custom-jobs describe "$JOB" --region=europe-west4 \
  --format="value(state, error.message)"                      # what failed, per Vertex
# healthy lifecycle: JOB_STATE_PENDING -> JOB_STATE_RUNNING -> JOB_STATE_SUCCEEDED
# real failures we hit:
#   JOB_STATE_FAILED  The replica workerpool0-0 exited with a non-zero status of 1.
#   JOB_STATE_FAILED  Replicas low on memory: workerpool0        (host-RAM OOM)
gcloud ai custom-jobs stream-logs "$JOB" --region=europe-west4     # live logs
gcloud logging read "resource.labels.job_id=\"${JOB##*/}\"" \
  --project=paligemma-scienceqa --limit=50   # past logs (numeric id = last path segment)
```

Hard-won practices baked into the scripts (each debugged a real failure here):

- **`PYTHONUNBUFFERED=1`** in the job scripts — a signal-killed process (OOM)
  loses its buffered stdout, so without this our first pruning crash logged
  *nothing*, not even a traceback.
- **CPU-only Vertex verify job** — a `n1-standard-4` job that just imports the
  package (~5 min, no GPU queue) caught an image-packaging bug that would
  otherwise cost a 16 h GPU-queue wait per attempt.
- **Fail-fast CUDA assert** at job start (see the training steps above).
- **`mypy` in CI** — it caught a call-signature bug in the GPU-only code path
  that unit tests structurally cannot execute.

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
# profile the training loop itself (Lightning profiler — 'simple' or 'advanced'):
uv run train trainer.profiler=simple trainer.fast_dev_run=true trainer.wandb.enabled=false
```

cProfile + per-worker-count timings; results in `reports/profiling/`. The
Lightning profiler prints its report when the run ends.

#### Distributed training, data, and model

None of the three is needed at this scale — **LoRA buys us out of all of
them** (full argument + measurements in
[`reports/RESULTS.md`](reports/RESULTS.md)):

- **Distributed (data-parallel) training / DDP** — everything fits one L4
  (~6.4 M trainable params). If more GPUs appeared, the switch is one Lightning
  line: `Trainer(devices=2, strategy="ddp")`.
- **Distributed data loading** — we parallelize *within* the node instead: the
  `DataLoader` runs with `num_workers: 2` (`configs/data/scienceqa.yaml`).
  Profiling shows ~11 ms/batch, fully overlapped by compute — sharded loading
  would solve a problem we measurably do not have (~700 MB dataset).
- **Distributed model (FSDP / tensor parallelism)** — the bf16 model is ~7 GB
  on a 24 GB L4, and LoRA training adds little on top (optimizer state only
  for adapter params, activations capped by gradient checkpointing). Nothing
  needs sharding; if it ever did, Lightning's FSDP/DeepSpeed strategies are a
  config change, not a rewrite.


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

The explicit method (what the wrapper does, minus image digest-pinning and
retries — all 8 template variables must be exported, or the rendered spec has
empty values and Vertex rejects it):

```bash
export IMAGE_URI=europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-train:latest \
       ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
       PRUNE_SPARSITIES=0.0,0.3,0.5,0.7 PRUNE_N_BATCHES=0 SKIP_BENCHMARK=0 \
       RUN_FINETUNE=0 FINETUNE_SPARSITY=0.5 FINETUNE_STEPS=300
envsubst < cloud/vertex_optimize.template.yaml > cloud/vertex_optimize.yaml
gcloud ai custom-jobs create --region=europe-west4 --project=paligemma-scienceqa \
  --display-name=paligemma-optimize --config=cloud/vertex_optimize.yaml
```

Inside the container, `cloud/run_optimize.sh` runs the underlying CLI. One
invocation benchmarks all three precision/compile configs — `bf16` (the
serving default), `int4` (bitsandbytes 4-bit), and `bf16+torch.compile`:

```bash
python -m scipali.models.optimize benchmark <adapter_dir> \
  --n-samples 8 --iters 5 --output-path optimize_results.json
# <adapter_dir>: checkpoints/opt-adapter in the job (downloaded from $ADAPTER_GCS);
#   locally: checkpoints/adapter-production
```

Measured result (full table in [`reports/RESULTS.md`](reports/RESULTS.md)):
**int4 halves peak GPU memory** (6.87 → 3.38 GB) for ~9 % latency cost, while
`torch.compile` matched bf16 latency but *raised* memory to 8.26 GB — no win
at this batch size.

#### Pruning sweep

```bash
# accuracy vs sparsity over the full test split (prune-only, fits a 32GB host)
SKIP_BENCHMARK=1 PRUNE_SPARSITIES=0.0,0.3,0.5,0.7 PRUNE_N_BATCHES=0 \
  TEMPLATE=cloud/vertex_optimize.template.yaml RENDERED=cloud/vertex_optimize.yaml \
  DISPLAY_NAME=paligemma-prune \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

The explicit method — identical to the benchmark above except
`SKIP_BENCHMARK=1` and the display name:

```bash
export IMAGE_URI=europe-west4-docker.pkg.dev/paligemma-scienceqa/mlops-images/paligemma-train:latest \
       ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
       PRUNE_SPARSITIES=0.0,0.3,0.5,0.7 PRUNE_N_BATCHES=0 SKIP_BENCHMARK=1 \
       RUN_FINETUNE=0 FINETUNE_SPARSITY=0.5 FINETUNE_STEPS=300
envsubst < cloud/vertex_optimize.template.yaml > cloud/vertex_optimize.yaml
gcloud ai custom-jobs create --region=europe-west4 --project=paligemma-scienceqa \
  --display-name=paligemma-prune --config=cloud/vertex_optimize.yaml
```

Inside the container, `cloud/run_optimize.sh` runs the underlying CLI:

```bash
python -m scipali.models.optimize prune-sweep <adapter_dir> \
  --sparsities 0.0,0.3,0.5,0.7 --output-path prune_results.json
# <adapter_dir> = local folder with the LoRA adapter. In the job it is
#   checkpoints/opt-adapter (run_optimize.sh downloads $ADAPTER_GCS there first);
#   the local equivalent is checkpoints/adapter-production
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

Once up: `curl localhost:8000/` for health, or open <http://localhost:8000/docs>
— FastAPI's interactive Swagger UI, where you can fire a `/predict` from the
browser.

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
curl "$API/"                       # health — model_loaded flips after the 1st predict
# -> {"status":"ok","model_loaded":"False"}
curl -s -X POST "$API/predict" -H 'Content-Type: application/json' -d '{
  "question": "What is the capital of Wyoming?",
  "choices": ["Phoenix", "Baton Rouge", "Honolulu", "Cheyenne"],
  "image_b64": "'"$(base64 < img.png | tr -d '\n')"'"}'
# -> {"prediction":"D"}
curl "$API/monitor/drift"          # Evidently drift check vs the seeded reference
# -> {"dataset_drift":false,"n_drifted_columns":0,"n_columns":...}
curl -s "$API/metrics" | head      # Prometheus metrics
```

#### Interpret prediction failures

Every failure mode we actually hit, as a diagnostic ladder — each symptom
means something different:

| Symptom | Meaning | Fix |
|---|---|---|
| `Connection refused` / "Backend unreachable" | Nothing is listening — server not started, crashed, or wrong port | Start the API; check `lsof -i :8000` |
| `{"detail":"Method Not Allowed"}` (405) | Path exists, wrong verb: a browser GET on `/predict`, or a POST silently downgraded to GET by the `http://`→`https://` 301 redirect | POST it (curl/UI/Swagger); always use `https://` exactly |
| `422 Unprocessable Entity` | Server healthy — the request body is invalid (missing `question` / `choices` / `image_b64`) | Fix the JSON payload |
| `{"detail":"Model checkpoint not loaded…"}` | Server was started without `CHECKPOINT_PATH` | Restart it with the env var set |
| Very slow first call / client timeout | Not an error: cold start (~150–230 s on scaled-to-zero Cloud Run; locally the first predict loads the 3B model) | Warm it with one request first |
| `429 Rate exceeded` | One heavy inference per instance (`concurrency=1`); overflow beyond `max-instances=3` is rejected | Retry — see [Load test](#load-test) |
| `5xx` | Real server-side failure | Check Cloud Run logs — this is exactly what the [5xx alert](#set-up-the-5xx-alert) emails about |

Working diagnosis order: *is anything listening? → right URL and verb? → valid
body? → is the model loaded? → is it just cold?* — each step's symptom is
unambiguous, so the ladder converges in five questions.

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

On success the terminal prints `Deploying container to Cloud Run service
[paligemma-api] in project [paligemma-scienceqa] region [europe-west4]` and
ends with the service URL — retrievable any time with:

```bash
gcloud run services describe paligemma-api --region=europe-west4 --format="value(status.url)"
```

The service is CPU-only (8 vCPU / 32 GB), `min-instances 0` (scale-to-zero)
with lazy model loading — an always-on GPU endpoint would cost more than a
course project justifies. Cold `/predict` runs ~150–230 s (container start +
model load + inference); warm calls ~25–80 s. Full latency breakdown in
[`docs/source/api.md`](docs/source/api.md); flag rationale in
[`docs/source/usage.md`](docs/source/usage.md#deploy-to-cloud-run).

Why Cloud Run and not Cloud Functions: this service is a long-lived container
with a multi-GB lazy-loaded model and pinned system deps — Cloud Run's exact
container model. Cloud Functions targets short stateless functions deployed
from source (its gen2 runtime is itself built on Cloud Run), so it adds
constraints here without adding anything.

#### Promote a new model to production

```bash
gcloud storage cp -r <new-adapter-dir> gs://mlops-paligemma-west4/models/production
```

Then move the W&B `production` alias to the new version (W&B UI). The registry
webhook fires the `model-registry-change` workflow, which rolls out a fresh
Cloud Run revision and smoke-tests it — **no image rebuild needed**.

<a id="zone-monitoring-ops"></a>
### Monitoring & operations [[Back To Contents]](#command-guide)

#### Data-drift report

```bash
# generate the Evidently HTML report (reference vs current split)
uv run --group serving python -m scipali.monitoring.monitoring drift
# -> writes reports/monitoring/drift_report.html, log line:
#    "Dataset drift detected: False | drifted columns: 0/<n>"
open reports/monitoring/drift_report.html

# the production loop behind /monitor/drift:
uv run --group serving python -m scipali.monitoring.monitoring collect \
  --project paligemma-scienceqa        # pull real /predict traffic from Cloud Logging -> GCS CSV
uv run --group serving python -m scipali.monitoring.monitoring seed-reference   # (re)build the reference CSV
```

The live service also exposes `/monitor/drift` (drift vs a seeded reference)
and Prometheus metrics at `/metrics`.

#### Load test

```bash
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 5 -r 1 -t 1m \
  --host https://paligemma-api-581237630637.europe-west4.run.app
```

Locust prints a stats table every few seconds and a final summary. Our
recorded run (2 users, 4 min — full analysis in `reports/load/README.md`)
ended like this:

```text
Type   Name        # reqs   # fails  |  Med     p95     Max
POST   /predict        24  13(54%)   |  10 s    27 s    27 s
GET    /               12   8(67%)   |  4.6 s   10 s    10 s
```

The 429 failures *were* the finding: the initial deploy (`--max-instances 1`,
`--concurrency 1`) served one request at a time and rejected the overflow —
which is why the service now runs `--max-instances 3`.

The same command works against the local API (start it first — see
[Serve the API locally](#serve-the-api-locally)); useful to demo the tool
without cloud access:

```bash
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 5 -r 1 -t 1m --host http://localhost:8000
```

#### Set up the 5xx alert

```bash
uv run python cloud/setup_monitoring.py   # idempotent: email channel + 5xx alert policy
# verify what exists (real output):
gcloud alpha monitoring policies list \
  --format="table(displayName,enabled,conditions[0].displayName)"
# -> paligemma-api server errors (5xx)  True  5xx responses > 0 over 5 min
gcloud alpha monitoring channels list \
  --format="table(displayName,type,verificationStatus)"
# -> paligemma-api alerts (email)  email  VERIFIED
```

The script talks to the Cloud Monitoring REST API with create-or-reuse
semantics, so rerunning it is always safe; the manual equivalent is
`gcloud alpha monitoring channels/policies create` from JSON files. The policy
fires on any 5xx from the API within a 5-minute window and emails the verified
channel (auto-closes after 30 min). Note `VERIFIED`: an email channel delivers
nothing until its verification code is confirmed — we verified it end-to-end
rather than assuming.

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

#### GCP billing: check, recover, rescue

```bash
gcloud billing accounts list
# -> ACCOUNT_ID           NAME                           OPEN
# -> 01AB7A-...           Billing Account for Education  True
# -> 01D0D9-...           (first education account)      False   <- the failed situation
gcloud billing projects describe paligemma-scienceqa --format="value(billingAccountName,billingEnabled)"
# -> billingAccounts/01AB7A-...  True
```

**The recoverable failure (we lived it):** our first education billing account
closed **mid-sweep** — Vertex killed the running trial (that is why
`sandy-sweep-7` has no training-time test score; see `reports/RESULTS.md`) and
new jobs were rejected. Nothing else was lost, because adapters + metrics
stream to W&B and data/models live in GCS. Recovery is one command once you
have another open account:

```bash
gcloud billing projects link paligemma-scienceqa --billing-account=<NEW-ACCOUNT-ID>
```

Relinking restores the *services*, not the killed *work*: the deployed Cloud
Run service resumes on its own, but Vertex jobs that died stay dead and queued
jobs are gone — rerun them (`bash cloud/watch_job.sh`). In our case the killed
trial's checkpoint had already been saved, so instead of retraining we
recovered its missing test score with a post-hoc standalone eval.

**If it cannot be recovered** (no open account): the project gets suspended
and later shut down. Rescue the irreplaceable artifacts while the bucket still
answers — everything else already lives outside GCP (git, W&B):

```bash
gcloud storage cp -r gs://mlops-paligemma-west4/models/production ~/mlops-adapter-backup
dvc pull                        # materialize the dataset locally
```

— then run the teardown below so nothing keeps billing.

#### Delete everything

Step-by-step removal of every billable/cloud resource this project created, in stop-the-billing-first order:

```bash
# 1. the serving endpoint (the always-reachable, per-request-billed piece)
gcloud run services delete paligemma-api --region=europe-west4

# 2. any queued/running Vertex jobs
gcloud ai custom-jobs list --region=europe-west4 --filter="state=JOB_STATE_PENDING"
gcloud ai custom-jobs cancel <job-id> --region=europe-west4

# 3. CI triggers (stop future builds)
gcloud builds triggers delete mlops-ci-api --region=europe-west4
gcloud builds triggers delete mlops-ci-train --region=europe-west4

# 4. container images
gcloud artifacts repositories delete mlops-images --location=europe-west4

# 5. storage — THIS DELETES THE DVC DATA + ALL ADAPTERS (backup exists at
#    ~/mlops-adapter-backup/); after this, `dvc pull` is dead
gcloud storage rm -r gs://mlops-paligemma-west4

# 6. secrets, alerting, and the deploy identity
gcloud secrets delete wandb-api-key && gcloud secrets delete hf-token
gcloud alpha monitoring policies list --format="value(name)"   # then: policies delete <id>
gcloud iam service-accounts delete gh-deployer@paligemma-scienceqa.iam.gserviceaccount.com
gcloud iam workload-identity-pools delete github-pool --location=global
```

Or the one-liner that does all of the above (30-day recovery window):

```bash
gcloud projects delete paligemma-scienceqa
```

Not deleted on purpose: the GitHub repo and the W&B project (free tier, and
they *are* the portfolio). Local cleanup: see
[Clean up docker resources](#clean-up-docker-resources).

---

Created using [mlops_template](https://github.com/SkafteNicki/mlops_template), a
[cookiecutter template](https://github.com/cookiecutter/cookiecutter) for MLOps.
