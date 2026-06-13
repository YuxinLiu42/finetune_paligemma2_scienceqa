# Usage

All commands assume the project environment is synced (`uv sync`).

## Data

```bash
# Download derek-thomas/ScienceQA (image questions) and preprocess the splits
uv run python -m project_name.data download
uv run python -m project_name.data preprocess --overwrite
dvc push   # publish processed data to the GCS remote
```

## Train (local)

```bash
uv run train trainer.wandb.enabled=true trainer.wandb.run_name=local-test
```

Hyperparameters live in `configs/` (Hydra). The learning rate is derived from
`model.base_learning_rate` via a sqrt batch-size rule unless set explicitly.

## Train + sweep on Vertex AI

```bash
# baseline + N-trial W&B sweep + by-subject eval, on one L4 (Flex Start queue)
bash cloud/watch_job.sh                         # full run
SKIP_BASELINE=1 bash cloud/watch_job.sh         # sweep only
```

## Evaluate an adapter

```bash
# local
uv run python -m project_name.evaluate checkpoints/adapter-production --by-subject
# standalone Vertex eval job against any GCS adapter
TEMPLATE=cloud/vertex_eval.template.yaml RENDERED=cloud/vertex_eval.yaml \
  DISPLAY_NAME=paligemma-eval \
  ADAPTER_GCS=gs://mlops-paligemma-west4/models/production \
  bash cloud/watch_job.sh
```

## Predict / serve

```bash
# single prediction
uv run python -m project_name.predict checkpoints/adapter-production \
  -q "What gas do plants absorb?" -c "oxygen,carbon dioxide,nitrogen" -i img.png

# API (local; PREDICT_DEVICE=cpu since MPS crashes on PaliGemma matmuls)
CHECKPOINT_PATH=checkpoints/adapter-production PREDICT_DEVICE=cpu \
  uv run uvicorn project_name.api:app --port 8000

# Streamlit frontend over the API
API_URL=http://localhost:8000 \
  uv run --group serving streamlit run src/project_name/frontend.py
```

## Ops

```bash
# data-drift report (Evidently)
uv run --group serving python -m project_name.monitoring
# load test the deployed API (locust)
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 5 -r 1 -t 1m --host <cloud-run-url>
# BentoML serving
uv run --group serving bentoml serve project_name.bento_service:ScienceQAService
```
