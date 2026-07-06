#!/usr/bin/env bash
# Shell demo of the deployed ScienceQA API: health -> predict -> drift.
#
# Usage:
#   ./cloud/demo_api.sh                          # auto-uses test sample 0
#   ./cloud/demo_api.sh IMG.png "Question?" "a,b,c"   # bring your own sample
#
# Override the backend with API_URL=... (defaults to the live Cloud Run service).
# The first /predict on a cold instance can take ~160s while the model loads.
set -euo pipefail

API_URL="${API_URL:-https://paligemma-api-581237630637.europe-west4.run.app}"
echo "Backend: ${API_URL}"

echo
echo "[1/3] GET /  (health — model_loaded is False until the first prediction):"
# A cold (scaled-to-zero) instance needs ~45s just to boot the container, so
# give the health check headroom and never let a timeout abort the demo — the
# predict step below has its own 600s budget that absorbs cold starts anyway.
curl -sS --max-time 90 "${API_URL}/" \
  || echo "  (health check timed out — instance still booting; continuing)"
echo

echo
echo "[2/3] POST /predict  (cold start can take ~160s):"
if [ "$#" -ge 3 ]; then
  # Bring-your-own sample: stdlib only, no project env needed.
  PAYLOAD="$(python3 - "$1" "$2" "$3" <<'PY'
import base64, json, sys
img, question, csv = sys.argv[1], sys.argv[2], sys.argv[3]
choices = [c.strip() for c in csv.split(",") if c.strip()]
sys.stderr.write(f"  question: {question}\n  choices:  {choices}\n")
print(json.dumps({
    "question": question,
    "choices": choices,
    "image_b64": base64.b64encode(open(img, "rb").read()).decode(),
}))
PY
)"
else
  # No args: pull test sample 0 from the processed dataset (needs the local venv).
  # The dataset carries the gold answer index, so the prediction is scored below.
  echo "  (no args — extracting test sample 0 from the processed dataset)"
  OUT="$(UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$HOME/.venvs/mlops}" \
    uv run --quiet python - <<'PY'
import base64, io, json, sys
from datasets import load_from_disk
from scipali.data.data import DATASET_SUBSET, PROCESSED_DATA_DIR
s = load_from_disk(PROCESSED_DATA_DIR / DATASET_SUBSET)["test"][0]
buf = io.BytesIO(); s["image"].convert("RGB").save(buf, format="PNG")
gold = chr(ord("A") + int(s["answer"]))
sys.stderr.write(f"  question: {s['question']}\n  choices:  {list(s['choices'])}\n")
print(json.dumps({
    "question": s["question"],
    "choices": list(s["choices"]),
    "image_b64": base64.b64encode(buf.getvalue()).decode(),
}))
print(gold)
PY
)"
  PAYLOAD="${OUT%%$'\n'*}"
  GOLD="${OUT##*$'\n'}"
fi

RESP="$(curl -s --max-time 600 -X POST "${API_URL}/predict" \
  -H 'Content-Type: application/json' -d "${PAYLOAD}")"
echo "  response: ${RESP}"
PRED="$(printf '%s' "${RESP}" | \
  python3 -c 'import json,sys; print(json.load(sys.stdin).get("prediction","?"))')"
echo "  -> predicted letter: ${PRED}"
if [ -n "${GOLD:-}" ]; then
  if [ "${PRED}" = "${GOLD}" ]; then
    echo "  -> ground truth:     ${GOLD} — CORRECT"
  else
    echo "  -> ground truth:     ${GOLD} — INCORRECT"
  fi
fi

echo
echo "[3/3] GET /monitor/drift  (real production table once traffic is collected):"
curl -s --max-time 180 "${API_URL}/monitor/drift"; echo
