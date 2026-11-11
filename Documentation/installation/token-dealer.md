# LLM access (token dealer): deployment

LLM access gives each student of an activity a personal API key for a course model, with token limits and a timetable set by the teacher. Students' requests do not go through LAMB. They go through a LiteLLM proxy that LAMB controls. Three services run next to LAMB:

| Service | What it does | Image |
|---------|--------------|-------|
| `token-dealer-proxy` | Checks every request's key, budgets and blocks, forwards it to the model | `ghcr.io/berriai/litellm:v1.102.1` (pinned by digest, amd64 and arm64) |
| `token-dealer-db` | The proxy's database: keys, teams, spend logs | `postgres:16.10-alpine` |
| `token-dealer-worker` | LAMB's worker: applies timetables and blocks to the keys every 10 s, reads usage into LAMB's ledger every 20 s | the LAMB image |

They are off by default. They start only when you add `docker-compose.token-dealer.yaml`.

## 1. Proxy configuration

```bash
cp token-dealer/config.example.yaml token-dealer/config.yaml
```

List the models students may use under `model_list`. The `model_name` is what students type in their tools; organization admins pick from these names. Keep the three prices on every model:

```yaml
      input_cost_per_token: 0.000001
      output_cost_per_token: 0.000001
      cache_read_input_token_cost: 0.000001
```

LAMB counts budgets in tokens by pricing one token at 0.000001. A model without a price skips every budget check, and unpriced cached tokens are not counted.

Provider keys go in `token-dealer/proxy.env` (for example `OPENAI_API_KEY=…`), read by the config as `os.environ/OPENAI_API_KEY`. Both `token-dealer/config.yaml` and `token-dealer/proxy.env` are ignored by git.

Keep `callbacks: lamb_token_messages.proxy_handler_instance`. That plugin (`backend/lamb/token_dealer/proxy/lamb_token_messages.py`, mounted by the Compose file) words refusals in tokens ("Token limit for this time slot reached: 3,112 of 3,000 tokens …"). Without it students see dollar amounts.

## 2. Variables

Add to `.env`:

| Variable | Required | Meaning |
|----------|----------|---------|
| `TOKEN_DEALER_MASTER_KEY` | yes | The proxy's master key, starting with `sk-`. LAMB uses it to create and block keys. Generate it, for example `echo "sk-$(openssl rand -hex 24)"`. |
| `TOKEN_DEALER_DB_PASSWORD` | yes | Password of the proxy's Postgres. |
| `TOKEN_DEALER_PUBLIC_URL` | yes | The address students paste into their tools, ending in `/v1`, for example `https://llm.lamb.example.com/v1`. |
| `TOKEN_DEALER_PROXY_URL` | no | How LAMB reaches the proxy's admin API. Default `http://token-dealer-proxy:4000`. |
| `TOKEN_DEALER_PORT` | no | Host port of the proxy, bound to 127.0.0.1 only. Default `4000`. |
| `TOKEN_DEALER_CONFIG` | no | Another path for the proxy configuration. Default `./token-dealer/config.yaml`. |
| `LLM_PUBLIC_HOST` | production | Host name of the students' endpoint, for Caddy, for example `llm.lamb.example.com`. |
| `TOKEN_DEALER_RECONCILE_SECONDS` | no | How often the worker re-checks every live key against timetables, default `30`. It also runs right after each minute mark, so timetables open and close on time whatever this is. Teachers' Block, Unblock, Close and Open reach the proxy at once and do not wait for it. |
| `TOKEN_DEALER_INGEST_SECONDS` | no | How often the worker copies usage from the proxy into LAMB, default `60`. Only the freshness of the usage figures depends on it; the proxy enforces every limit itself. |
| `TOKEN_DEALER_INGEST_OVERLAP_SECONDS` | no | How far back each copy re-reads, default `600`. Spend logs carry the start time of their request, so it must exceed your longest request (long agent requests with large contexts). Larger values re-read more rows. |
| `TOKEN_DEALER_BUDGET_RESET_MIN_SECONDS`, `…_MAX_SECONDS` | no | How often LiteLLM refills expired slot budgets, default `10` and `15`. Longer means students wait longer after a slot boundary. |

These variables are the default connection of every organization. The system administrator can override them per organization in Org Admin → Settings → LLM access.

## 3. Start

```bash
docker compose -f docker-compose.next.yaml -f docker-compose.token-dealer.yaml up -d
```

Production, with Caddy and TLS:

```bash
docker compose -f docker-compose.next.yaml -f docker-compose.next.prod.yaml \
  -f docker-compose.token-dealer.yaml -f docker-compose.token-dealer.prod.yaml up -d
```

The production overlay adds a site for `LLM_PUBLIC_HOST` that forwards `/v1/` to the proxy and answers 404 to everything else. The proxy's admin routes (`/key`, `/team`, `/user`, `/spend`, `/ui`) are never public; LAMB reaches them inside the Compose network. Point the DNS name at the server before starting, as for the other hosts.

Behind Apache or nginx instead of Caddy, forward `https://<llm host>/v1/` to `http://127.0.0.1:4000/v1/` and nothing else. Turn off response buffering on that location: answers stream.

## 4. Check

| Check | Expect |
|-------|--------|
| `docker compose … ps` | `token-dealer-proxy` healthy, `token-dealer-worker` running |
| `curl -s http://127.0.0.1:4000/health/liveliness` on the server | `"I'm alive!"` |
| Org Admin → Settings → LLM access, as system administrator | "Proxy: connected, reachable" and the models from `config.yaml` |
| `docker compose … logs token-dealer-worker` | no repeated errors |
| `curl -s https://<llm host>/key/list` | 404 (admin routes are not public) |

Then the organization admin switches LLM access on and chooses models. See the user guides for the rest.

## 5. Operation

- **One worker per deployment.** It holds a lock on the ledger; a second worker exits at once. For a single pass by hand (after a restore, for example), stop it first: `docker compose … stop token-dealer-worker`, `docker compose … run --rm --no-deps token-dealer-worker --once`, `docker compose … start token-dealer-worker`.
- **Timing.** Defaults are production values. Development and test rigs may set `TOKEN_DEALER_RECONCILE_SECONDS=10` and `TOKEN_DEALER_INGEST_SECONDS=20` for quick results. **Usage figures** reach the teacher's page up to the ingest interval plus 30 seconds after a request (90 s by default): the proxy writes spend logs in batches, 10 to 30 s after the request. The teacher's page states the delay from the same setting.
- **Cost of a worker cycle.** One query reads the live keys of active activities and the keys of archived activities not yet closed; the proxy is called only for keys whose state must change. Measured on synthetic data (21 October 2026): 34 ms per quiet cycle with 60,000 keys, of which 6,000 in active activities.
- **The ledger** is `token_dealer_usage.db` in LAMB's data volume, next to LAMB's database. Back it up with it.
- **More than one proxy instance** needs Redis, or each instance keeps its own view of budgets and blocks. Uncomment `coordination_redis` and `enable_redis_auth_cache` in `config.yaml` and add a Redis service.
- **Slot budgets** refill within seconds of the slot boundary because the Compose file sets `PROXY_BUDGET_RESCHEDULER_MIN_TIME=10` and `MAX_TIME=15`. Without them the proxy checks about every ten minutes.

## 6. Upgrades

- **LAMB:** rebuild or pull the LAMB image and recreate `lamb` and `token-dealer-worker` together; they must run the same version.
- **LiteLLM:** the image is pinned to the version LAMB was load-tested against (v1.102.1). Before changing the pin, check in a test deployment that the slot, total and pool limits still refuse, that the refusal is still worded in tokens (the plugin uses the proxy's failure hook), and that blocking a key takes effect within 10 seconds. Back up the proxy's database first: LiteLLM migrates its schema on start.
- **Postgres:** a minor version change (16.x) needs nothing; a major version change needs a dump and restore.
