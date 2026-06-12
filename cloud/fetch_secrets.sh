# Resolve WANDB_API_KEY / HF_TOKEN inside the Vertex container.
#
# Source this file (don't execute it): `. cloud/fetch_secrets.sh`
# Values are fetched from Secret Manager so job specs carry only secret NAMES
# (previously the values sat in plaintext, visible via `gcloud ai custom-jobs
# describe`). Skipped for any variable that is already exported (e.g. local
# runs). Requires the job's service account to hold
# roles/secretmanager.secretAccessor on the secrets.
#
# Auth goes through google.auth ADC — the same path dvc/gcs use successfully
# in this container. A raw curl of metadata.google.internal returned an empty
# body on Vertex (job 4716516618115481600 died on it), so do NOT "simplify"
# this back to curl. Retries cover the metadata server not being ready in the
# first seconds after container start.
#
# Env vars (all optional):
#   GCP_PROJECT        project owning the secrets (default paligemma-scienceqa)
#   WANDB_SECRET_NAME  secret holding the W&B key (default wandb-api-key)
#   HF_SECRET_NAME     secret holding the HF token (default hf-token)

GCP_PROJECT="${GCP_PROJECT:-paligemma-scienceqa}"
WANDB_SECRET_NAME="${WANDB_SECRET_NAME:-wandb-api-key}"
HF_SECRET_NAME="${HF_SECRET_NAME:-hf-token}"

_fetch_secret_once() {
  python - <<'PY'
import base64
import json
import os
import urllib.request

import google.auth
import google.auth.transport.requests

creds, _ = google.auth.default(
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)
creds.refresh(google.auth.transport.requests.Request())
project = os.environ["GCP_PROJECT"]
name = os.environ["SECRET_NAME"]
url = (
    "https://secretmanager.googleapis.com/v1/"
    f"projects/{project}/secrets/{name}/versions/latest:access"
)
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {creds.token}"})
payload = json.load(urllib.request.urlopen(req, timeout=30))
print(base64.b64decode(payload["payload"]["data"]).decode())
PY
}

fetch_secret() {
  local name="$1" attempt value
  for attempt in 1 2 3 4 5; do
    if value="$(SECRET_NAME="${name}" GCP_PROJECT="${GCP_PROJECT}" _fetch_secret_once)"; then
      printf '%s' "${value}"
      return 0
    fi
    echo ">>> fetch of ${name} failed (attempt ${attempt}/5) — retrying in 10s" >&2
    sleep 10
  done
  echo "!!! could not fetch secret ${name} from Secret Manager" >&2
  return 1
}

if [ -z "${WANDB_API_KEY:-}" ]; then
  echo ">>> fetching ${WANDB_SECRET_NAME} from Secret Manager"
  WANDB_API_KEY="$(fetch_secret "${WANDB_SECRET_NAME}")"
  export WANDB_API_KEY
fi
if [ -z "${HF_TOKEN:-}" ]; then
  echo ">>> fetching ${HF_SECRET_NAME} from Secret Manager"
  HF_TOKEN="$(fetch_secret "${HF_SECRET_NAME}")"
  export HF_TOKEN
fi
