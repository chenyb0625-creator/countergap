"""Build a self-contained, offline `demo.html` from the real run outputs.

Embeds the toy corpus, the seven method traces, and the provisional automated
evaluations into a single static page (no CDN, no network). Re-run after any
experiment to refresh the demo.

Usage:  python scripts/build_demo_html.py [--output demo.html]
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from countergap.adapters.literature import LocalFrozenCorpusBackend
from countergap.evaluation.temporal_split import temporal_split
from countergap.schemas import Document


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect(tag: str = "demo", corpus_path: Path | None = None, cutoff_iso: str = "2022-12-31") -> dict:
    corpus_path = corpus_path or ROOT / "data" / "demo_corpus.jsonl"
    docs = [
        Document.model_validate_json(line)
        for line in corpus_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    cutoff = date.fromisoformat(cutoff_iso)
    pre, post = temporal_split(docs, cutoff)
    pre_ids = {d.document_id for d in pre}
    corpus = [
        {
            "id": d.document_id,
            "title": d.title,
            "abstract": d.abstract,
            "date": d.publication_date.isoformat(),
            "tags": d.tags,
            "period": "pre-cutoff (visible)" if d.document_id in pre_ids else "post-cutoff (hidden)",
        }
        for d in sorted(docs, key=lambda x: x.publication_date)
    ]

    traces: dict[str, dict] = {}
    for trace_path in sorted((ROOT / "outputs").glob(f"{tag}_*_trace.jsonl")):
        records = load_jsonl(trace_path)
        method = records[0]["metadata"]["method_name"]
        traces[method] = {"records": records, "path": trace_path.name}

    evaluations: dict[str, dict] = {}
    for eval_path in sorted((ROOT / "outputs").glob(f"{tag}_*_trace.evaluation.jsonl")):
        record = json.loads(eval_path.read_text(encoding="utf-8").splitlines()[0])
        method = record["run_id"].split("-")[1]
        evaluations[method] = {
            "verdict": record["evaluation"]["verdict"],
            "score_vector": record["evaluation"]["score_vector"],
            "aggregate": record["aggregate_score"],
        }
    return {"cutoff": cutoff.isoformat(), "corpus": corpus, "traces": traces, "evaluations": evaluations}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CounterGap Demo — Temporal Falsifiable Evaluation of Research-Gap Agents</title>
<style>
  :root {{
    --bg:#f6f7f9; --card:#ffffff; --ink:#1c2430; --muted:#5b6572; --line:#e3e7ec;
    --accent:#2f6fed; --good:#1a7f4b; --warn:#b45309; --bad:#b91c1c; --chip:#eef2f7;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.65 -apple-system,"Segoe UI","Microsoft YaHei",Roboto,sans-serif; }}
  .wrap {{ max-width:1060px; margin:0 auto; padding:28px 20px 80px; }}
  header {{ background:linear-gradient(135deg,#16305c,#2f6fed); color:#fff; border-radius:16px;
           padding:30px 32px; margin-bottom:26px; }}
  header h1 {{ margin:0 0 8px; font-size:26px; letter-spacing:.2px; }}
  header p {{ margin:2px 0; color:#dbe6ff; font-size:14px; }}
  .tag {{ display:inline-block; background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.35);
         border-radius:999px; padding:2px 12px; font-size:12px; margin-right:8px; }}
  section {{ background:var(--card); border:1px solid var(--line); border-radius:14px;
             padding:22px 24px; margin-bottom:22px; }}
  h2 {{ margin:0 0 14px; font-size:19px; }}
  h2 small {{ color:var(--muted); font-weight:400; font-size:13px; margin-left:8px; }}
  table {{ border-collapse:collapse; width:100%; font-size:13.5px; }}
  th,td {{ text-align:left; padding:7px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
  .mono {{ font-family:Consolas,Menlo,monospace; font-size:12.5px; }}
  .pill {{ display:inline-block; border-radius:999px; padding:1px 10px; font-size:12px; font-weight:600; }}
  .pill.pre {{ background:#e7f3ec; color:var(--good); }}
  .pill.post {{ background:#fdeaea; color:var(--bad); }}
  .pill.outcome {{ background:var(--chip); color:var(--ink); }}
  .pill.outcome.ok {{ background:#e7f3ec; color:var(--good); }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; }}
  .card {{ border:1px solid var(--line); border-radius:12px; padding:14px 16px; background:#fbfcfe; }}
  .card .name {{ font-weight:700; font-size:14px; }}
  .card .meta {{ color:var(--muted); font-size:12.5px; margin-top:4px; }}
  .card .agg {{ font-size:22px; font-weight:700; margin-top:8px; }}
  .bar {{ height:8px; background:#e9edf3; border-radius:99px; overflow:hidden; margin-top:6px; }}
  .bar > i {{ display:block; height:100%; background:var(--accent); border-radius:99px; }}
  .trace-step {{ border-left:3px solid var(--line); padding:4px 0 4px 16px; margin:8px 0; position:relative; }}
  .trace-step.search {{ border-color:var(--accent); }}
  .trace-step.read {{ border-color:#0891b2; }}
  .trace-step.propose_gap {{ border-color:var(--warn); }}
  .trace-step.search_counterevidence {{ border-color:#9333ea; }}
  .trace-step.stop {{ border-color:var(--good); }}
  .trace-step .k {{ font-size:11px; color:var(--muted); font-weight:700; }}
  .trace-step .q {{ font-size:13px; }}
  .trace-step .exp {{ font-size:12px; color:var(--muted); }}
  code {{ background:#eef1f5; border-radius:5px; padding:1px 6px; font-size:12.5px;
         font-family:Consolas,Menlo,monospace; }}
  pre {{ background:#0f172a; color:#dbe6ff; border-radius:10px; padding:14px 16px; overflow:auto;
        font-size:12.5px; line-height:1.6; }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; }}
  @media (max-width:820px) {{ .grid2 {{ grid-template-columns:1fr; }} }}
  .note {{ background:#fff8e6; border:1px solid #f0dcae; border-radius:10px; padding:12px 14px;
          font-size:13px; color:#6b4d0a; }}
  .foot {{ color:var(--muted); font-size:12.5px; text-align:center; margin-top:26px; }}
</style>
</head>
<body>
<div class="wrap">

<header>
  <h1>CounterGap — 研究缺口发现智能体的时间冻结评测环境</h1>
  <p><span class="tag">{corpus_tag}</span><span class="tag">cutoff {cutoff}</span>
     <span class="tag">8 methods</span><span class="tag">DeepSeek LLM 可选</span></p>
  <p style="margin-top:10px">核心问题：在时间冻结的文献环境下，主动反证搜索能否减少虚假研究缺口主张？
     本 demo 展示管线、各方法轨迹与评分（自动 rubric，非人工评审）。</p>
</header>

<section>
  <h2>1 · 冻结语料 <small>{corpus_desc}</small></h2>
  <table>
    <tr><th>ID</th><th>标题</th><th>日期</th><th>状态</th></tr>
    {corpus_rows}
  </table>
</section>

<section>
  <h2>2 · 方法对比 <small>同一语料 · 同一 cutoff · 同一 seed · 同一动作预算</small></h2>
  <div class="cards">{method_cards}</div>
</section>

<section>
  <h2>3 · 评分对比 <small>provisional automated rubric（countergap_auto_v1），非人工评审</small></h2>
  <table>
    <tr><th>方法</th><th>终态判定</th><th>novelty</th><th>evidence</th><th>robust</th><th>future</th><th>repro</th><th>aggregate</th></tr>
    {score_rows}
  </table>
  <div class="note" style="margin-top:12px">{note_html}</div>
</section>

<section>
  <h2>4 · 示例探索轨迹 <small>llm_counter_search（DeepSeek 驱动）—— 完整可审计动作序列</small></h2>
  <div id="trace">{trace_steps}</div>
  <p style="color:var(--muted);font-size:12.5px;margin-bottom:0">
    每步动作、查询、暴露文档均记录在 JSONL trace 中（{trace_path}），
    可复核"反证搜索是否真实发生、主张是否基于已读证据"。</p>
</section>

<section>
  <h2>5 · 复现与限制</h2>
  <div class="grid2">
    <div>
      <h2 style="font-size:15px">复现命令</h2>
      <pre>python scripts/build_demo_corpus.py
python scripts/run_demo.py            # 4 个确定性方法
python scripts/run_llm_demo.py        # 7 个方法（含 DeepSeek）
python scripts/score_trace.py --trace outputs/demo_*_trace.jsonl
pytest                                # 34 tests</pre>
    </div>
    <div>
      <h2 style="font-size:15px">API Key 安全</h2>
      <pre># .env（已被 .gitignore 排除，绝不入库）
DEEPSEEK_API_KEY=sk-...  </pre>
      <p style="font-size:13px;color:var(--muted)">Key 只存在于本地 .env，不进入 trace、prompt 或 git 提交。
         缺少 key 时确定性方法照常运行。详见 docs/llm_integration.md。</p>
      <p style="font-size:13px;color:var(--muted)">⚠️ 任何科学结论前仍需按 AGENTS.md §8 人工检查 ≥20 条 trace；
         未来发表 ≠ 缺口为真，仅作离线佐证。</p>
    </div>
  </div>
</section>

<div class="foot">CounterGap · M0 完成 · M1/M2 LLM 化 · M3 真实语料待定 · 生成自 scripts/build_demo_html.py</div>
</div>
</body>
</html>
"""


def method_card(name: str, info: dict, evaluation: dict | None) -> str:
    outcome = info.get("terminal_outcome") or "?"
    ok = outcome == "validated_candidate_gap"
    agg = evaluation["aggregate"] if evaluation else None
    steps = info.get("steps")
    return f"""<div class="card">
      <div class="name">{name}</div>
      <div class="meta">{info.get('kind', '')}</div>
      <div><span class="pill outcome {'ok' if ok else ''}">{outcome}</span></div>
      <div class="agg">{f"{agg:.3f}" if agg is not None else "—"}</div>
      <div class="bar"><i style="width:{int((agg or 0) * 100)}%"></i></div>
      <div class="meta">{steps} actions · seed 42 · budget 16</div>
    </div>"""


def trace_steps_html(records: list[dict]) -> str:
    out = []
    for record in records:
        if record.get("record_type") != "action":
            continue
        event = record["event"]
        action = event["action"]
        a_type = action["type"]
        payload = action["payload"]
        step = event["step"]
        exposed = event.get("exposed_document_ids") or []
        label = {
            "search": "support search",
            "search_counterevidence": "counter-evidence search",
            "read": "read",
            "propose_gap": "propose gap",
            "revise_gap": "revise gap",
            "reject_gap": "reject gap",
            "abandon_gap": "abandon",
            "stop": "stop",
        }.get(a_type, a_type)
        if a_type in ("search", "search_counterevidence"):
            detail = f"<span class='q'>“{payload.get('query')}”</span>"
            if exposed:
                detail += f" <span class='exp'>→ exposed {', '.join(exposed)}</span>"
        elif a_type == "read":
            detail = f"<span class='q'>doc {payload.get('document_id')}</span>"
        elif a_type in ("propose_gap", "revise_gap", "reject_gap", "abandon_gap", "stop"):
            detail = f"<span class='q'>{payload.get('text', payload.get('reason', ''))}</span>"
        else:
            detail = ""
        out.append(
            f"<div class='trace-step {a_type}'><span class='k'>step {step} · {label}</span><br>{detail}</div>"
        )
    return "".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "demo.html")
    parser.add_argument("--tag", default="demo", help="trace prefix (demo | real)")
    parser.add_argument("--corpus", type=Path, default=None)
    parser.add_argument("--cutoff", default="2022-12-31")
    parser.add_argument("--title-suffix", default="玩具语料")
    args = parser.parse_args()

    data = collect(tag=args.tag, corpus_path=args.corpus, cutoff_iso=args.cutoff)
    cutoff = data["cutoff"]
    trace_label = args.tag
    # For large real corpora, render a bounded preview of the corpus table.
    corpus_preview = data["corpus"][:15]
    corpus_hidden = len(data["corpus"]) - len(corpus_preview)
    corpus_rows = "".join(
        f"<tr><td class='mono'>{d['id'][:38]}</td><td>{d['title'][:90]}<br>"
        f"<span style='color:var(--muted);font-size:12px'>{d['abstract'][:160]}{'…' if len(d['abstract']) > 160 else ''}</span></td>"
        f"<td class='mono'>{d['date']}</td>"
        f"<td><span class='pill {('pre' if d['period'].startswith('pre') else 'post')}'>{d['period']}</span></td></tr>"
        for d in corpus_preview
    )
    if corpus_hidden > 0:
        corpus_rows += (
            f"<tr><td colspan='4' style='color:var(--muted);font-size:12px'>"
            f"… 另有 {corpus_hidden} 篇未在表格中展示（完整列表见语料 JSONL）</td></tr>"
        )

    kinds = {
        "random": "随机基线",
        "keyword_trend": "关键词/趋势基线",
        "one_shot": "一次性启发式",
        "no_counter_search": "无反证搜索消融",
        "counter_search": "确定性反证搜索智能体",
        "embedding_boundary": "嵌入边界基线（词袋代理）",
        "one_shot_llm": "一次性 LLM（DeepSeek）",
        "llm_counter_search": "交互式 LLM 反证搜索智能体（DeepSeek）",
    }
    summaries: dict[str, dict] = {}
    for name, t in data["traces"].items():
        summaries[name] = t["records"][-1]["summary"]
    info_by_method: dict[str, dict] = {}
    for name, t in data["traces"].items():
        s = summaries[name]
        info_by_method[name] = {
            "terminal_outcome": s.get("terminal_outcome"),
            "steps": len([r for r in t["records"] if r.get("record_type") == "action"]),
            "kind": kinds.get(name, ""),
        }

    order = ["random", "keyword_trend", "one_shot", "no_counter_search", "counter_search",
             "embedding_boundary", "one_shot_llm", "llm_counter_search"]
    method_cards = "".join(
        method_card(name, info_by_method[name], data["evaluations"].get(name)) for name in order
    )

    score_rows = "".join(
        "<tr>"
        f"<td>{name}</td>"
        f"<td><span class='pill outcome {'ok' if data['evaluations'].get(name, {}).get('verdict') == 'validated_candidate_gap' else ''}'>"
        f"{data['evaluations'].get(name, {}).get('verdict', 'n/a')}</span></td>"
        + "".join(
            f"<td class='mono'>{v:.2f}</td>" if isinstance(v, float) else f"<td class='mono'>{v}</td>"
            for v in [
                data["evaluations"].get(name, {}).get("score_vector", {}).get("pre_cutoff_novelty"),
                data["evaluations"].get(name, {}).get("score_vector", {}).get("evidence_quality"),
                data["evaluations"].get(name, {}).get("score_vector", {}).get("counterevidence_robustness"),
                data["evaluations"].get(name, {}).get("score_vector", {}).get("future_emergence"),
                data["evaluations"].get(name, {}).get("score_vector", {}).get("reproducibility"),
            ]
        )
        + f"<td class='mono'><b>{data['evaluations'].get(name, {}).get('aggregate', 0):.3f}</b></td>"
        "</tr>"
        for name in order
    )

    trace_steps = trace_steps_html(data["traces"]["llm_counter_search"]["records"])

    is_real = args.tag == "real"
    if is_real:
        corpus_tag = "real corpus (OpenAlex CC0)"
        note_html = (
            "<b>解读注意</b>：在真实语料（326 篇，cutoff 2024-06-30）上，交互式 LLM 智能体"
            "提出主张 → 生成证伪查询 → 找到 2 篇 pre-cutoff 已有文献 → <b>撤回主张</b>"
            "（no_validated_gap，counterexample discovery，robustness=1.0）。"
            "一次性 LLM 提出同类主张却无法验证。这是机制演示（单 seed），不代表统计结论；"
            "LLM 运行非确定性；future 列仅为自动化词重叠，不是 ground truth。"
        )
    else:
        corpus_tag = "toy corpus"
        note_html = (
            "<b>解读注意</b>：玩具语料上只有交互式 LLM 智能体产出 <b>validated_candidate_gap</b>"
            "（提出主张 → 生成证伪查询 → 在冻结语料中搜索反证 → 判断主张存活 → 对最终假设再做"
            "支持+反证搜索后才停止）。一次性 LLM 只能提出同样的主张却无法验证 —— 这正是本环境要"
            "暴露的对比。LLM 运行非确定性（单 seed 演示）；自动 rubric 对模糊表述的 novelty 打分"
            "偏高；future 列仅为自动化词重叠，不是 ground truth。"
        )
    corpus_desc = (
        f"{len(data['corpus'])} 篇文档 · cutoff {cutoff} · "
        f"{sum(1 for d in data['corpus'] if d['period'].startswith('pre'))} 篇可见 / "
        f"{sum(1 for d in data['corpus'] if not d['period'].startswith('pre'))} 篇隐藏"
    )

    html = HTML_TEMPLATE.format(
        cutoff=cutoff,
        corpus_tag=corpus_tag,
        corpus_desc=corpus_desc,
        note_html=note_html,
        trace_path=f"outputs/{args.tag}_llm_counter_search_trace.jsonl",
        corpus_rows=corpus_rows,
        method_cards=method_cards,
        score_rows=score_rows,
        trace_steps=trace_steps,
    )
    args.output.write_text(html, encoding="utf-8")
    print(f"Wrote {args.output} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
