# Sampling parameters (pin these at the SERVING layer)

The kit's co-primary open models are **GLM-5.1** and **Qwen3-Coder-Next**. Sampling (temperature,
top_p, top_k, …) is a property of the **inference server / request**, not of the agent's config file —
so pin it in your vLLM/SGLang launch flags or your hosted-provider request defaults. The agent configs
(`pi/models.json`, `qwen/.qwen/settings.json`, `crush.json`, `opencode.json`) only carry the endpoint,
model id, and context/output sizes.

> Use the **official model-card values below**. Don't lower temperature "for determinism" — both
> vendors tuned these for agentic/tool-calling quality, and Qwen3-Coder in particular degrades tool
> calling at off-spec sampling. Only deviate with a measured reason.

## Qwen3-Coder-Next  (Alibaba/Qwen — non-thinking)
Official model-card "Best Practices":

| Param | Value |
|---|---|
| temperature | **1.0** |
| top_p | **0.95** |
| top_k | **40** |
| repetition_penalty | not specified (leave default) |
| max output tokens | **65536** (recommended) |
| context window | **262144** native (drop to 32768 on OOM) |
| thinking | none — does **not** emit `<think>` blocks; rely on the kit's explicit phases |
| vLLM/SGLang | `--tool-call-parser qwen3_coder` (required for function calling) |

> Don't confuse with **Qwen3-Coder-30B-A3B-Instruct**, which uses `temp 0.7 / top_p 0.8 / top_k 20 /
> repetition_penalty 1.05`. If you serve the 30B instead, use those.

## GLM-5.1  (Z.ai / Zhipu — thinking by default)
Z.ai does **not** publish a single crisp "recommended sampling" line for 5.1; these synthesize the
GLM-5.1 eval configs + the documented GLM-4.x family convention (the official fallback baseline).

| Param | Value | Source |
|---|---|---|
| temperature | **1.0** | GLM-5.1 eval config + GLM-4.6 official |
| top_p | **0.95** | GLM-5.1 eval config + GLM-4.6 official |
| top_k | **40** | GLM-4.6 official (Z.ai API has no top_k; use 40 only for local vLLM/SGLang) |
| max output tokens | **65536** default (up to 131072, ≥1024) | Z.ai param guide (GLM-5.x) |
| context window | check your deployment (GLM-5 family ≥200K) | deployment-dependent |
| thinking | enabled by default; `reasoning_effort: max` or `high`; disable with `enable_thinking=false` | GLM-5.1 docs |

> **⚠ Verify against the live GLM-5.1 model card / Z.ai docs before production** — 5.1 is new and Z.ai
> may publish exact params. The Z.ai API guidance is to set **only one** of `temperature`/`top_p`.
> For OpenAI-compatible routing of GLM via pi, set `compat.thinkingFormat: "zai"` (already in
> `pi/models.json`); for Qwen set `"qwen-chat-template"`.

## Example vLLM launch (self-hosted)
```bash
# Qwen3-Coder-Next
vllm serve Qwen/Qwen3-Coder-Next \
  --served-model-name Qwen3-Coder-Next \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --max-model-len 262144
# Then set per-request defaults temperature=1.0 top_p=0.95 top_k=40 (client or gateway).
```
A hosted provider (z.ai / DeepInfra / Together) needs none of this — just set
`OPENAI_BASE_URL` + `OPENAI_API_KEY` + `OPENAI_MODEL` in `.env`.
