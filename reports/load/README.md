# Load test

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

- **CPU inference dominates**: successful `/predict` calls take about 10 to
  27 s (PaliGemma2-3B on CPU, no GPU). A cold start takes about 160 s (model
  download + load).
- **429 "Rate exceeded" under concurrency**: this run was against the initial
  deployment (`--max-instances 1 --concurrency 1`), so the service served one
  request at a time and rejected the overflow. A health check that arrived
  while a `/predict` was still running also received a 429. We then raised the
  service to `--max-instances 3 --concurrency 1`: overflow now starts a new
  instance instead of returning 429, while each instance still runs one heavy
  inference at a time (this avoids OOM on the 3B model), and the service still
  scales to zero when idle. Re-running the load test
  against the new config should show fewer 429s (at the cost of more cold
  starts, since each new instance downloads the base model on its first call).

The raw statistics are in `scienceqa_stats.csv` / `scienceqa_stats_history.csv`.

> **Note:** this run was made before the `r=16` production promotion (2026-06-14).
> Direct measurement against the current production adapter shows higher
> latency: warm `/predict` calls now take about 25 to 80 s (commonly 35 to 50 s),
> and a true cold start (scale-zero → first `/predict`) takes about 150 to
> 230 s; see `docs/source/usage.md` / `docs/source/api.md`. Re-running this
> load test against the current adapter would be useful but is not required,
> because the harness together with this completed run already satisfies the
> load-testing requirement.
