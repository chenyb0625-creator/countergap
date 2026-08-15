# LLM integration (DeepSeek)

CounterGap keeps the base repository runnable **without any API key**
(AGENTS.md §9). Model integrations are optional and sit behind a small
interface, so the evaluation protocol never depends on a commercial API.

## Where the API key goes

The key is read from the `DEEPSEEK_API_KEY` environment variable, which the
tiny loader in `src/countergap/config.py` populates from a **gitignored**
`.env` file at the repository root.

```bash
cp .env.example .env
# edit .env, set:
#   DEEPSEEK_API_KEY=sk-your-deepseek-key-here
```

Rules enforced by the repository:

- `.env` is in `.gitignore`; a real key must never be committed.
- `.env.example` contains only a placeholder.
- The key is never written into traces, prompts, or run summaries.
- If `DEEPSEEK_API_KEY` is missing, LLM methods fail with a clear message and
  the deterministic methods still run.

Optional overrides (also in `.env`):

```text
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/chat/completions
```

## Interface

`src/countergap/adapters/llm.py` defines:

```python
class LLMClient(Protocol):
    def complete(self, system: str, user: str, *,
                 temperature: float = 0.2, max_tokens: int = 1024) -> str: ...
```

`DeepSeekClient` implements it with the Python standard library only
(`urllib`); no extra dependency is required. Anything implementing the
protocol can be swapped in (a local Ollama endpoint, another OpenAI-compatible
service, or a scripted fake in tests).

LLM-driven methods:

- `baselines/one_shot_llm.py` — one-shot gap generation (M1 baseline).
- `agents/llm_counter_search.py` — interactive agent whose proposal,
  falsification queries, and revise/reject/retain verdicts come from the model
  (M2). Every LLM call has a deterministic fallback so a model failure never
  crashes the run.

Prompt construction (`agents/prompts.py`) uses only documents the agent has
already observed through the environment; post-cutoff material can never reach
the model.

## Running

```bash
python scripts/run_llm_demo.py            # all 7 methods, DeepSeek included
python scripts/run_llm_demo.py --skip-llm # deterministic methods only
python scripts/run_llm_demo.py --budget 16 --seed 42
```

LLM methods are **not deterministic** (sampling temperature); for any
quantitative comparison, run multiple seeds and treat single traces as
illustrative only. `scripts/score_trace.py` marks LLM reproducibility as 0.5
until a multi-seed check is performed.

## Scoring traces (offline, post-run)

```bash
python scripts/score_trace.py --trace outputs/demo_llm_counter_search_trace.jsonl
```

`score_trace.py` writes an `offline_evaluation` record with
`evaluator_id="countergap_auto_v1"` — an explicit, formula-based proxy, **not**
a human review. Per AGENTS.md §8, manual trace inspection is still required
before any scientific claim. Use `reviewer.html` (or your own review JSON) for
the human step.
