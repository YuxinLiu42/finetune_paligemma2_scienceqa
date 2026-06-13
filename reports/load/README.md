# Load test (M24)

`tests/load/locustfile.py` run against the Cloud Run service
(`https://paligemma-api-...europe-west4.run.app`), 2 users, 4 minutes:

```bash
uv run --group serving locust -f tests/load/locustfile.py \
  --headless -u 2 -r 1 -t 4m --host <cloud-run-url> --csv reports/load/scienceqa
```

## Findings

| Endpoint | Requests | Failures | Median | p95 | Max |
|---|---|---|---|---|---|
| POST /predict | 24 | 13 (429) | 10 s | 27 s | 27 s |
| GET / | 12 | 8 (429) | 4.6 s | 10 s | 10 s |

- **CPU inference dominates**: successful `/predict` calls take ~10–27 s
  (PaliGemma2-3B on CPU, no GPU). Cold start is ~160 s (model download + load).
- **429 "Rate exceeded" under concurrency**: the service is deployed with
  `--max-instances 1 --concurrency 1` (cost-controlled, scale-to-zero), so it
  serializes requests and rejects the overflow. Raising concurrency/instances
  (or moving to a GPU) would lift throughput at higher cost.

Raw stats in `scienceqa_stats.csv` / `scienceqa_stats_history.csv`.
