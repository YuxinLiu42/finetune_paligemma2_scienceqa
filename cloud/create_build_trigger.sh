#!/usr/bin/env bash
# Continuous containers: the TWO Cloud Build push triggers on this repo, as
# 2nd-gen GitHub triggers in europe-west4 (matching the rest of the project):
#
#   mlops-ci-api    ENABLED   cloud/cloudbuild.api.yaml
#       rebuilds + pushes the API image on every push to `main` touching
#       src/scipali/** (or the build config itself).
#   mlops-ci-train  DISABLED on purpose   cloud/cloudbuild.train.yaml
#       the train image installs a locally-built wheel from wheelhouse/
#       (git-ignored), which a bare CI checkout does not have, so a push-
#       triggered build can only fail (see dockerfiles/train.dockerfile).
#       The trigger exists for symmetry/documentation; the image is built
#       manually: uv build --wheel -o wheelhouse && gcloud builds submit
#       --config=cloud/cloudbuild.train.yaml .
#
# This script recreates that state idempotently (describe || create). NOTE:
# the original live pair was created via the console on 2026-06-16; the live
# mlops-ci-train is a 1st-gen trigger still naming the repo's pre-rename id
# (SS26_MLOps_Project_GroupA) — harmless while disabled, and GitHub redirects
# renamed repos. This script leaves existing triggers untouched (except for
# re-asserting that mlops-ci-train is disabled).
#
# ── PREREQUISITES ──
#  * The build configs on origin/main — a trigger reads its build config from
#    the repo at build time.
#  * The Cloud Build P4SA needs Secret Manager perms (2nd-gen stores the GitHub
#    OAuth token there). One-time:
#      gcloud projects add-iam-policy-binding "$PROJECT" \
#        --member="serviceAccount:service-<PROJECT_NUMBER>@gcp-sa-cloudbuild.iam.gserviceaccount.com" \
#        --role=roles/secretmanager.admin --condition=None
#  * You need ADMIN on the GitHub repo to install the Cloud Build GitHub App.
#
# Idempotent. The GitHub OAuth can't be scripted: on the first run this creates
# the connection and prints the authorization link; after you authorize in the
# browser, re-run it to link the repo and create the triggers.
set -euo pipefail

PROJECT="${PROJECT:-paligemma-scienceqa}"
REGION="${REGION:-europe-west4}"            # 2nd-gen triggers live in this region
CONNECTION="${CONNECTION:-paligemma-gh}"
REPO_OWNER="${REPO_OWNER:-yuxinliu42}"
REPO_NAME="${REPO_NAME:-finetune_paligemma2_scienceqa}"
REPO_RES="${REPO_RES:-${REPO_NAME}}"        # repo resource name on the connection
REMOTE_URI="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
REPO_RESOURCE="projects/${PROJECT}/locations/${REGION}/connections/${CONNECTION}/repositories/${REPO_RES}"

# 1. Host connection (GitHub App OAuth).
if ! gcloud builds connections describe "$CONNECTION" \
       --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  echo ">>> creating Cloud Build GitHub connection '$CONNECTION' in $REGION ..."
  gcloud builds connections create github "$CONNECTION" \
    --region="$REGION" --project="$PROJECT"
fi

STAGE="$(gcloud builds connections describe "$CONNECTION" \
  --region="$REGION" --project="$PROJECT" \
  --format='value(installationState.stage)' 2>/dev/null || true)"
if [ "$STAGE" != "COMPLETE" ]; then
  echo
  echo "!!! ACTION REQUIRED — authorize Cloud Build to access GitHub (needs admin"
  echo "    on ${REPO_OWNER}/${REPO_NAME}). Open and complete this link, then re-run:"
  gcloud builds connections describe "$CONNECTION" \
    --region="$REGION" --project="$PROJECT" \
    --format='value(installationState.actionUri)'
  exit 0
fi

# 2. Link the specific repository to the connection.
if ! gcloud builds repositories describe "$REPO_RES" \
       --connection="$CONNECTION" --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
  echo ">>> linking repository ${REPO_OWNER}/${REPO_NAME} ..."
  gcloud builds repositories create "$REPO_RES" \
    --remote-uri="$REMOTE_URI" --connection="$CONNECTION" \
    --region="$REGION" --project="$PROJECT"
fi

# 3. The two push triggers (mirrors the live pair's config).
ensure_trigger() {  # <name> <build-config> <included-files>
  local name="$1" config="$2" files="$3"
  if gcloud builds triggers describe "$name" \
       --region="$REGION" --project="$PROJECT" >/dev/null 2>&1; then
    echo ">>> trigger '$name' already exists — leaving it as-is"
    return 0
  fi
  echo ">>> creating trigger '$name' ($config) ..."
  gcloud builds triggers create github \
    --name="$name" \
    --project="$PROJECT" --region="$REGION" \
    --repository="$REPO_RESOURCE" \
    --branch-pattern='^main$' \
    --build-config="$config" \
    --included-files="$files"
}

ensure_trigger mlops-ci-api   cloud/cloudbuild.api.yaml   'src/scipali/**,cloud/cloudbuild.api.yaml'
ensure_trigger mlops-ci-train cloud/cloudbuild.train.yaml 'src/scipali/**,cloud/cloudbuild.train.yaml'

# 4. Keep mlops-ci-train DISABLED (`triggers create` has no --disabled flag, so
#    export -> set disabled -> import; import updates in place via the id field).
TRAIN_YAML="$(mktemp)"
gcloud builds triggers describe mlops-ci-train \
  --region="$REGION" --project="$PROJECT" --format=yaml > "$TRAIN_YAML"
if grep -qE '^disabled: true' "$TRAIN_YAML"; then
  echo ">>> mlops-ci-train already disabled"
else
  printf 'disabled: true\n' >> "$TRAIN_YAML"
  gcloud builds triggers import \
    --region="$REGION" --project="$PROJECT" --source="$TRAIN_YAML"
  echo ">>> mlops-ci-train disabled"
fi
rm -f "$TRAIN_YAML"

echo
echo "Triggers now live:"
gcloud builds triggers list --region="$REGION" --project="$PROJECT" \
  --format="table(name,disabled,filename)"
echo
echo "Fire the API build once now to verify (without waiting for a push):"
echo "  gcloud builds triggers run mlops-ci-api --region=$REGION --branch=main --project=$PROJECT"
