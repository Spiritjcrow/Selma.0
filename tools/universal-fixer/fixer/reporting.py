"""Read-only report generators. Never render issue body/HTML as trusted markup."""
import html
import json
from pathlib import Path
from .core import utcnow

def generate(registry, outdir):
    target=Path(outdir);target.mkdir(parents=True,exist_ok=True)
    items=registry.list_items()
    clean=[{k:v for k,v in item.items() if k not in ("decision_digest",)} for item in items]
    (target/"inventory.json").write_text(json.dumps({"generated_at":utcnow(),"source":"GitHub REST or explicit import","count":len(clean),"items":clean},indent=2),encoding="utf8")
    rows=["# Selma Universal Fixer inventory","",f"Generated: {utcnow()}",f"Entries: {len(items)}","","**Source status ≠ production readiness.** No check was assumed PASS. All approvals are for read-only review only.","","| Priority | Repository | Item | Title | Review decision |","|---|---|---|---|---|"]
    for x in items:
        title=x["title"].replace("|","\\|").replace("\n"," ")
        rows.append(f"| {x['priority']} | {x['repository']} | [#{x['number']}]({x['url']}) {x['kind']} | {title} | {x['decision'] or 'NONE'} |")
    (target/"inventory.md").write_text("\n".join(rows)+"\n",encoding="utf8")
    cards=[]
    for x in items:
        d=html.escape(x["decision"] or "AWAITING_REVIEW")
        cards.append(f'<article class="task" data-search="{html.escape((x["repository"]+" "+x["title"]+" "+x["priority"]).lower(),quote=True)}">'
                     f'<small>{html.escape(x["priority"])} · {html.escape(x["repository"])} · {html.escape(x["kind"])} #{x["number"]}</small>'
                     f'<h3><a href="{html.escape(x["url"],quote=True)}" rel="noopener noreferrer">{html.escape(x["title"])}</a></h3>'
                     f'<p>{d} · Tests: unverified by inventory</p></article>')
    body='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Selma Fixer — Evidence Inventory</title>
<style>body{font:16px system-ui;background:#091322;color:#eaf4ff;max-width:1050px;margin:auto;padding:1.5rem}a{color:#82d8ff}input{width:100%;padding:1rem;background:#17263b;color:white;border:1px solid #4e627d;border-radius:12px;box-sizing:border-box}article{border:1px solid #39506a;border-radius:14px;padding:1rem;margin:12px 0;background:#112238}small{color:#b6d0e5}h3{margin:.4rem 0}p{margin:.2rem 0;color:#c1d0de}.note{border-left:4px solid #9ad8ff;padding:.75rem 1rem;background:#152b42}</style>
<h1>Selma° Universal Fixer</h1><p class="note">Read-only inventory. Missing live evidence is never replaced with mock data. This page has no permission to run commands, approve purchases, or merge PRs. Use the local CLI for A/B/C/D review decisions.</p>
<input id="filter" type="search" aria-label="Filter by repository, title or priority" placeholder="Filter live inventory"><p id="count"></p><main id="tasks">'''+"".join(cards)+'''</main><script>
const input=document.getElementById('filter'),cards=[...document.querySelectorAll('.task')],count=document.getElementById('count');function apply(){let q=input.value.toLowerCase().trim(),shown=0;for(let c of cards){let yes=c.dataset.search.includes(q);c.hidden=!yes;if(yes)shown++}count.textContent=`${shown} of ${cards.length} items`;}
input.addEventListener('input',apply);apply();</script></html>'''
    (target/"index.html").write_text(body,encoding="utf8")
    return len(items)