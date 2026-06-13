"""FastAPI inference service for PaliGemma2 ScienceQA predictions."""

import base64
import io
import logging
import os
import tempfile
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from rich.logging import RichHandler

from project_name.model import PaliGemmaModule
from project_name.predict import load_model, predict_single

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler()],
)
log = logging.getLogger(__name__)

_module: PaliGemmaModule | None = None
_load_lock = threading.Lock()


def _fetch_gcs_dir(uri: str) -> Path:
    """Download a GCS directory (e.g. the production adapter) to a temp dir.

    Lets the serving container start from the stable GCS path
    (gs://mlops-paligemma-west4/models/production) instead of baking the
    adapter into the image — promotion then needs no rebuild/redeploy.

    Args:
        uri: gs://bucket/prefix directory holding the adapter files.

    Returns:
        Local directory containing the downloaded files.

    Raises:
        FileNotFoundError: If no objects exist under the prefix.
    """
    from google.cloud import storage  # type: ignore[attr-defined]

    parsed = urlparse(uri)
    prefix = parsed.path.lstrip("/").rstrip("/") + "/"
    dest_root = Path(tempfile.mkdtemp(prefix="adapter-"))
    client = storage.Client()
    count = 0
    for blob in client.list_blobs(parsed.netloc, prefix=prefix):
        rel = blob.name[len(prefix) :]
        if not rel:
            continue
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(dest))
        count += 1
    if not count:
        raise FileNotFoundError(f"No objects found under {uri}")
    log.info("Fetched %d adapter files from %s", count, uri)
    return dest_root


def _load_module() -> PaliGemmaModule | None:
    """Resolve ``CHECKPOINT_PATH`` and load the model, or return None.

    The path may be a LoRA adapter directory, a full .ckpt file, or a gs://
    directory (downloaded to a temp dir first). Returns None (rather than
    raising) when the variable is unset or the path is missing, so the service
    can still start and report its state via the health endpoint.
    """
    checkpoint_env = os.environ.get("CHECKPOINT_PATH", "")
    if not checkpoint_env:
        log.warning("CHECKPOINT_PATH not set — /predict will return 503.")
        return None
    if checkpoint_env.startswith("gs://"):
        log.info("CHECKPOINT_PATH is a GCS uri — downloading %s", checkpoint_env)
        checkpoint_path = _fetch_gcs_dir(checkpoint_env)
    else:
        checkpoint_path = Path(checkpoint_env)
    if not checkpoint_path.exists():
        log.warning("CHECKPOINT_PATH is set but path not found: %s", checkpoint_path)
        return None
    log.info("Loading model from %s ...", checkpoint_path)
    module = load_model(checkpoint_path)
    log.info("Model ready.")
    return module


def _ensure_loaded() -> PaliGemmaModule | None:
    """Return the model, loading it once on first use (thread-safe).

    Used by lazy loading: on Cloud Run, downloading + loading a 3B model can
    exceed the startup-probe window, so we defer it to the first request
    instead of blocking container startup.
    """
    global _module
    if _module is None:
        with _load_lock:
            if _module is None:
                _module = _load_module()
    return _module


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model on startup, unless ``LAZY_LOAD`` defers it to first use.

    Default (local, tests): eager load so the model is ready before serving.
    With ``LAZY_LOAD=1`` (Cloud Run): skip the load so the container binds the
    port immediately and passes the startup probe; the first /predict request
    triggers the (slow) load via ``_ensure_loaded``.

    Args:
        app: The FastAPI application instance (required by the lifespan protocol).
    """
    global _module
    if os.environ.get("LAZY_LOAD", "").lower() in ("1", "true", "yes"):
        log.info("LAZY_LOAD set — deferring model load to the first request.")
    elif os.environ.get("CHECKPOINT_PATH", ""):
        _module = _load_module()
    else:
        log.warning("CHECKPOINT_PATH not set — /predict will return 503.")

    yield

    _module = None
    log.info("Model released.")


app = FastAPI(
    title="PaliGemma2 ScienceQA API",
    description="Single-sample inference endpoint for "
    "PaliGemma2 fine-tuned on ScienceQA.",
    version="0.1.0",
    lifespan=lifespan,
)


class PredictRequest(BaseModel):
    """Request body for the /predict endpoint.

    Attributes:
        question: The question text.
        choices: List of answer choice strings (2–10 items).
        hint: Optional hint text appended to the prompt.
        lecture: Optional lecture text appended to the prompt.
        image_b64: Required base64-encoded image string (JPEG or PNG).
        max_new_tokens: Maximum number of tokens the model may generate.
    """

    question: str = Field(..., min_length=1, description="Question text.")
    choices: list[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="Answer choices, e.g. ['True', 'False'] or ['A', 'B', 'C'].",
    )
    hint: str = Field(default="", description="Optional hint text. Skipped if empty.")
    lecture: str = Field(
        default="", description="Optional lecture text. Skipped if empty."
    )
    image_b64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded image (JPEG or PNG).",
    )
    max_new_tokens: int = Field(
        default=10, ge=1, le=128, description="Max tokens to generate."
    )


class PredictResponse(BaseModel):
    """Response body for the /predict endpoint.

    Attributes:
        prediction: Predicted answer letter, e.g. "A" or "B".
    """

    prediction: str = Field(..., description="Predicted answer letter (A/B/C/D/...).")


@app.get("/", summary="Health check")
def root() -> dict[str, str]:
    """Return service status and whether the model is loaded.

    Returns:
        A dict with ``status`` and ``model_loaded`` keys.
    """
    return {
        "status": "ok",
        "model_loaded": str(_module is not None),
    }


@app.post(
    "/predict",
    response_model=PredictResponse,
    summary="Run inference on a single sample",
)
def predict(request: PredictRequest) -> PredictResponse:
    """Run single-sample inference and return the predicted answer letter.

    The image must be base64-encoded JPEG or PNG.
    The prediction is a single letter (A, B, C, ...) corresponding to the
    index of the predicted choice in ``request.choices``.

    Args:
        request: PredictRequest containing the question, choices, and
            optional image and hint.

    Returns:
        PredictResponse with the predicted answer letter.

    Raises:
        HTTPException 503: Model checkpoint has not been loaded.
        HTTPException 400: Image decoding failed.
    """
    module = _ensure_loaded()
    if module is None:
        raise HTTPException(
            status_code=503,
            detail="Model checkpoint not loaded. "
            "Please set CHECKPOINT_PATH and restart the service.",
        )

    # Decode the image (required — PaliGemma is image-conditioned)
    try:
        image_bytes = base64.b64decode(request.image_b64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to decode image_b64: {exc}",
        ) from exc

    # Only forward optional fields that were actually provided,
    # matching whatever columns survived --drop-cols during preprocessing.
    prompt_kwargs: dict[str, str] = {}
    if request.hint:
        prompt_kwargs["hint"] = request.hint
    if request.lecture:
        prompt_kwargs["lecture"] = request.lecture

    prediction = predict_single(
        module=module,
        image=image,
        question=request.question,
        choices=request.choices,
        max_new_tokens=request.max_new_tokens,
        **prompt_kwargs,
    )

    log.info(
        "Prediction complete | question: %.60s | prediction: %s",
        request.question,
        prediction,
    )
    return PredictResponse(prediction=prediction)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
