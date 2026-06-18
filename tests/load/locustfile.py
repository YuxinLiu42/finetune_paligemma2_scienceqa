r"""Locust load test for the ScienceQA API.

Hits /predict with a fixed sample so we can measure latency/throughput under
concurrency. A 3B model on CPU is seconds-per-request, so run with a small
user count and read the percentile latencies rather than chasing high RPS.

Run (against a local server or the Cloud Run URL):
    uv run --group serving locust -f tests/load/locustfile.py \\
      --headless -u 5 -r 1 -t 1m --host http://localhost:8000
"""

import base64
import io

from locust import HttpUser, between, task
from PIL import Image

# A tiny synthetic image keeps the request small; the model still runs a full
# forward+generate, which is what we are timing.
_buf = io.BytesIO()
Image.new("RGB", (224, 224), "white").save(_buf, format="PNG")
_IMAGE_B64 = base64.b64encode(_buf.getvalue()).decode()

_PAYLOAD = {
    "question": "Which property do these objects have in common?",
    "choices": ["soft", "salty", "sticky"],
    "hint": "",
    "lecture": "",
    "image_b64": _IMAGE_B64,
}


class PredictUser(HttpUser):
    """A user that repeatedly calls /predict and checks the health endpoint."""

    wait_time = between(1, 3)

    @task(5)
    def predict(self) -> None:
        """POST a sample to /predict; long timeout covers cold-start model load."""
        with self.client.post(
            "/predict", json=_PAYLOAD, timeout=600, catch_response=True
        ) as resp:
            if resp.status_code == 200 and len(resp.json().get("prediction", "")) == 1:
                resp.success()
            else:
                resp.failure(f"bad response: {resp.status_code} {resp.text[:120]}")

    @task(1)
    def health(self) -> None:
        """Lightweight health poll."""
        self.client.get("/", timeout=30)
