# scipali: Answer Your Science Questions

[![Unit Tests](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/tests.yaml/badge.svg)](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/tests.yaml)
[![Code linting](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/linting.yaml/badge.svg)](https://github.com/yuxinliu42/finetune_paligemma2_scienceqa/actions/workflows/linting.yaml)
[![codecov](https://codecov.io/gh/yuxinliu42/finetune_paligemma2_scienceqa/graph/badge.svg)](https://codecov.io/gh/yuxinliu42/finetune_paligemma2_scienceqa)


PaliGemma2-3B fine-tuned with LoRA on ScienceQA-IMG, built into a full MLOps
pipeline: DVC data versioning, Hydra configs, W&B sweeps, Vertex AI training,
Cloud Run serving, drift monitoring, and CI/CD. The main result is **72.19%**
exact-match accuracy on the 2,017-sample test split.

<p align="center">
  <img src="reports/figures/randomQ_ui.png" alt="Streamlit UI: a ScienceQA test sample answered correctly by the deployed model" width="720">
</p>

*The deployed model in the Streamlit UI ("Pick from ScienceQA" mode): for a
test sample it predicts "A — chirping", which the UI marks as correct against
the ground truth.*


## Project description

### Goal
The project has two goals: to improve the reasoning accuracy of the pretrained
PaliGemma foundation model on multimodal science questions, and to do this
inside a complete, reproducible MLOps pipeline: versioned data, configurable
training, tracked experiments, automated deployment, and monitoring.

### Framework
We use the Hugging Face Transformers framework. We build on its main
strength, the access to thousands of pretrained models, by starting from a
pretrained PaliGemma2 checkpoint and fine-tuning it on our data instead of
training anything from scratch. Around it we use PEFT/LoRA for
parameter-efficient fine-tuning, PyTorch Lightning for the training loop, and
Hydra for configuration management.

### Use case & target users
Given a science question, a supporting image, and a set of answer choices, the
model picks the correct answer. The intended users are students and
educational tools (ScienceQA contains grade-school science material); within
this course, however, the served model is mainly the workload that exercises
the pipeline. It is deployed behind a FastAPI service on Cloud Run with a
Streamlit UI on top. Details and variants are in
[`docs/source/usage.md`](docs/source/usage.md); the results the commands
produce are in [`reports/RESULTS.md`](reports/RESULTS.md).

### Dataset
[`derek-thomas/ScienceQA`](https://huggingface.co/datasets/derek-thomas/ScienceQA),
the image subset ("ScienceQA-IMG"): train 6,218 / val 2,097 / test 2,017. Each
sample has an image, a question, answer choices, the answer index, and optional
hint / lecture plus a subject label. (We initially planned `lmms-lab/ScienceQA`,
but that mirror provides no train split, so we switched.)

### Model
The PaliGemma2-3B vision-language model
([`google/paligemma2-3b-pt-224`](https://huggingface.co/google/paligemma2-3b-pt-224)),
LoRA-adapted on the language-model attention projections (`q/k/v/o_proj`) with
the vision encoder frozen: ~6.4 M trainable parameters against ~3 B frozen.

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
├── COMMANDS.md             # copy-paste command guide for every routine operation
├── pyproject.toml
└── tasks.py                # invoke tasks
```

The `src/scipali` package started from the template's flat module layout
(`data.py`, `model.py`, `train.py`, `evaluate.py`, `api.py`, `visualize.py`).
Those files grew during the project, so we applied the template's own
refactoring advice and moved them into subpackages of the same name:

* `data/`: everything related to the data. `data.py` downloads ScienceQA-IMG,
  preprocesses it into `data/processed`, and provides the dataset and collate
  interface that training and evaluation import; `profile_data.py` profiles
  the dataloader.
* `models/`: `model.py` defines the LoRA-wrapped PaliGemma2 Lightning module;
  `train.py` trains it (Hydra-configured, logged to W&B) using the data
  interface from `data/`; `evaluate.py` scores a trained adapter on the test
  split; `optimize.py` benchmarks quantization and pruning; `visualize.py`
  renders the report figures from the evaluation outputs.
* `serving/`: `api.py` is the FastAPI service that loads the promoted adapter
  and serves predictions; `predict.py` is a standalone prediction CLI;
  `frontend.py` is the Streamlit UI on top of the API; `bento_service.py` is
  the BentoML serving alternative.
* `monitoring/`: `monitoring.py` derives drift features, collects production
  traffic back from Cloud Logging, and builds the Evidently drift report that
  the `/monitor/drift` endpoint serves.

## Architecture

<img src="reports/figures/architecture.jpg" alt="System architecture" width="700" height="332">

The end-to-end pipeline: data is versioned with DVC (bytes in GCS, pointers in
git); training runs as a Vertex AI custom job on a single L4 GPU, configured
by Hydra and tracked in W&B; promoting a model in the W&B registry triggers an
automatic Cloud Run rollout; the deployed FastAPI service logs every
prediction, which feeds the drift monitoring. Solid arrows show the main
artifact flow, dashed arrows the two automated feedback loops (auto-deploy on
promotion, drift feedback from production logs).

## Quick start

The minimal path from a fresh clone to a working system:

```bash
# 1. clone and create the environment (uv, Python 3.11)
git clone https://github.com/yuxinliu42/finetune_paligemma2_scienceqa.git
cd finetune_paligemma2_scienceqa
uv sync

# 2. fetch the processed dataset (DVC remote on GCS; needs `gcloud auth login`)
dvc pull

# 3. check that everything works: 132 CPU-only tests
uv run pytest tests/

# 4. ask the DEPLOYED model a question (public endpoint, no credentials needed)
./cloud/demo_api.sh              # health -> predict -> drift; cold start takes 2-4 min

# 5. or serve the API locally, then open http://localhost:8000/docs
uv run inv serve-api

# 6. training smoke run (one batch; real training runs on Vertex AI)
uv run train trainer.fast_dev_run=true trainer.wandb.enabled=false
```

Steps 5 and 6 need access to the gated PaliGemma2 base model (a Hugging Face
token); a W&B login is only needed for tracked training runs. All other
operations (Docker images, Vertex AI training and sweeps, deployment,
monitoring, billing, and teardown) are in the [command guide](COMMANDS.md).


---

Created using [mlops_template](https://github.com/SkafteNicki/mlops_template), a
[cookiecutter template](https://github.com/cookiecutter/cookiecutter) for MLOps.
