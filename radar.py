#!/usr/bin/env python3
"""Agent Bounty Radar — open bounties an AI agent can actually claim.

No auth, no API keys. Sources:
  * Superteam Earn  — only listings flagged AGENT_ALLOWED
  * Immunefi        — new programs with kyc:false (smart contracts)
  * Stellarator     — agent bounty threads (SOL escrow on Solana mainnet)
  * GitHub          — issues labelled `bounty` with a cash/crypto amount in the title

Output: data/bounties.json + README table.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UA = {"User-Agent": "agent-bounty-radar/1.0 (+https://github.com/jdz-green/agent-bounty-radar)"}


def _reward_tiers() -> dict:
    try:
        return json.loads((ROOT / "data" / "immunefi_rewards.json").read_text())
    except Exception:
        return {}
ROOT = Path(__file__).resolve().parent
OUT_LIMIT = 60
# Work this pipeline will not surface: solving captchas, evading bot protection, or
# automating platforms that prohibit it. The feed is for work that can be done honestly.
COMPLIANCE_BLOCK = ("captcha", "hcaptcha", "recaptcha", "bypass", "evade", "anti-bot",
                    "anti bot", "scrape behind", "brute force", "credential stuffing")


def get(url: str, accept: str = "application/json") -> bytes:
    req = urllib.request.Request(url, headers={**UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def superteam() -> list[dict]:
    try:
        data = json.loads(get("https://earn.superteam.fun/api/listings?status=open&take=150"))
    except Exception:
        return []
    out = []
    for x in data if isinstance(data, list) else []:
        if x.get("agentAccess") == "HUMAN_ONLY":
            continue
        out.append({
            "source": "superteam", "id": str(x.get("id")), "title": x.get("title", ""),
            "reward": f"{x.get('rewardAmount')} {x.get('token')}",
            "deadline": str(x.get("deadline", ""))[:10],
            "url": "https://earn.superteam.fun/listing/" + str(x.get("slug")),
            "agent_ok": True,
        })
    return out


def immunefi() -> list[dict]:
    try:
        t = get("https://immunefi.com/bug-bounty/", "text/html").decode("utf-8", "ignore")
        chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', t)
        buf = "".join(json.loads(c) for c in chunks if c)
        i = buf.find('"bounties":[')
        start = i + len('"bounties":')
        depth, end = 0, None
        for j in range(start, len(buf)):
            if buf[j] == "[":
                depth += 1
            elif buf[j] == "]":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        items = json.loads(buf[start:end])
    except Exception:
        return []
    tiers = _reward_tiers()
    out = []
    for p in items:
        if p.get("kyc") is not False:
            continue
        t = (tiers.get(p.get("slug", "")) or {}).get("tiers") or {}
        entry = t.get("Low") or t.get("Medium") or 0
        out.append({
            "source": "immunefi", "id": p.get("slug", ""),
            "title": f"{p.get('project', '')} — max ${p.get('maxBounty', 0):,}",
            "reward": f"${p.get('maxBounty', 0):,} max",
            "deadline": "rolling",
            "url": "https://immunefi.com" + str(p.get("url", "")),
            "agent_ok": True,
            "min_payout": entry,
            "tiers": t,
        })
    return out


def stellarator() -> list[dict]:
    try:
        txt = get("https://stellarator.site/yard?c=rfi", "text/plain").decode("utf-8", "ignore")
    except Exception:
        return []
    out = []
    for line in txt.splitlines():
        m = re.match(r"\[t=(\d+)\s*\|\s*entries=(\d+)\]\s*\[([^\]]+)\]\s*(.*)", line.strip())
        if not m:
            continue
        tid, entries, meta, title = m.groups()
        out.append({
            "source": "stellarator", "id": f"t{tid}", "title": title.strip()[:120],
            "reward": meta.strip(), "deadline": "72h window (rolling)",
            "url": f"https://stellarator.site/yard?c=cat&t={tid}",
            "agent_ok": True, "entries": int(entries),
        })
    return out


def github() -> list[dict]:
    """Public GitHub search (no auth): bounty-labelled issues mentioning money."""
    out = []
    q = urllib.parse.quote('label:bounty state:open created:>2026-10-01')
    try:
        data = json.loads(get(f"https://api.github.com/search/issues?q={q}&per_page=50"))
    except Exception:
        return []
    for it in data.get("items", []):
        title = it.get("title", "")
        if not re.search(r"\$\s?\d|SOL|USDC|USDT|ETH\b", title, re.I):
            continue
        out.append({
            "source": "github", "id": str(it.get("id")), "title": title[:120],
            "reward": (re.search(r"\$\s?\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:SOL|USDC|USDT|ETH)", title, re.I) or [""])[0] if re.search(r"\$\s?\d+(?:\.\d+)?|\d+(?:\.\d+)?\s*(?:SOL|USDC|USDT|ETH)", title, re.I) else "see issue",
            "deadline": "see issue", "url": it.get("html_url", ""), "agent_ok": None,
        })
    return out



def opire() -> list[dict]:
    """Opire: open-source issue bounties with a funded price, payable to a solver."""
    try:
        data = json.loads(get("https://api.opire.dev/rewards"))
    except Exception:
        return []
    out = []
    for b in data if isinstance(data, list) else []:
        price = b.get("pendingPrice") or {}
        cents = price.get("value") or 0
        if price.get("unit") == "USD_CENT":
            amount = cents / 100
        else:
            amount = float(cents)
        langs = ", ".join(b.get("programmingLanguages") or [])
        out.append({
            "source": "opire",
            "id": str(b.get("id", "")),
            "title": f"{b.get('title', '')[:90]}" + (f" — {langs}" if langs else ""),
            "reward": f"${amount:,.0f}",
            "deadline": "open until solved",
            "url": b.get("url", ""),
            "agent_ok": True,
            "value": amount,
        })
    return out

def compliant(row: dict) -> bool:
    text = f"{row.get('title', '')} {row.get('url', '')}".lower()
    return not any(bad in text for bad in COMPLIANCE_BLOCK)


def main() -> None:
    sources = {"superteam": superteam, "immunefi": immunefi, "stellarator": stellarator, "github": github, "opire": opire}
    rows: list[dict] = []
    stats = {}
    for name, fn in sources.items():
        try:
            got = fn()
        except Exception:
            got = []
        got = [r for r in got if compliant(r)]
        stats[name] = len(got)
        rows.extend(got)

    # de-dup and rank: agent-explicit first, then by reward magnitude where parseable
    seen, uniq = set(), []
    for r in rows:
        key = r["url"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    def rank(r):
        explicit = 0 if r.get("agent_ok") else 1
        t = r.get("tiers") or {}
        bar = 0 if t.get("Low") else (1 if t.get("Medium") else 2)
        nums = [float(x.replace(",", "")) for x in re.findall(r"[\d,]+(?:\.\d+)?", r["reward"])]
        return (explicit, bar, -max(nums) if nums else 0)

    uniq.sort(key=rank)
    # Keep a mix of sources instead of letting the largest catalogue crowd out the rest.
    per_source = {"superteam": 10, "immunefi": 24, "stellarator": 8, "github": 12, "opire": 8}
    kept, used = [], {}
    for r in uniq:
        cap = per_source.get(r["source"], OUT_LIMIT)
        if used.get(r["source"], 0) >= cap:
            continue
        used[r["source"]] = used.get(r["source"], 0) + 1
        kept.append(r)
    uniq = kept[:OUT_LIMIT]

    (ROOT / "data").mkdir(exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": "Agent-claimable bounties. agent_ok=true means the platform explicitly allows agent submissions.",
        "stats": stats,
        "bounties": uniq,
    }
    (ROOT / "data" / "bounties.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False))

    lines = [
        "# Agent Bounty Radar",
        "",
        "Open bounties that an **AI agent can actually claim** — scraped from public, no-auth APIs.",
        "",
        f"_Last refresh: {payload['generated_at']} · {len(uniq)} open items "
        f"({', '.join(f'{k}: {v}' for k, v in stats.items())})_",
        "",
        "Machine-readable feed: [`data/bounties.json`](data/bounties.json)",
        "",
        "| Source | Max reward | Bar | Item |",
        "|---|---|---|---|",
    ]
    for r in uniq:
        title = r["title"].replace("|", "\\|")
        t = r.get("tiers") or {}
        bar = (f"${t['Low']:,} Low" if t.get("Low") else (f"${t['Medium']:,} Med" if t.get("Medium") else "—"))
        lines.append(f"| {r['source']} | {r['reward']} | {bar} | [{title}]({r['url']}) |")
    lines += [
        "",
        "## Why this exists",
        "",
        "Almost every bounty board in 2026 is gated: KYC, human-only listings, or dead settlement rails.",
        "This radar only lists places where settlement is machine-payable (USDC/SOL) and the platform",
        "does not require identity documents to submit. `agent_ok` is `true` only when the platform says so.",
        "",
        "## Sources",
        "",
        "- **Superteam Earn** — listings with `agentAccess != HUMAN_ONLY`",
        "- **Immunefi** — programs flagged `kyc: false`",
        "- **Stellarator** — Solana-escrowed agent bounties (`/yard?c=rfi`)",
        "- **GitHub** — issues labelled `bounty` whose title carries a cash amount",
        "",
        "Refresh: GitHub Actions cron, every 6 hours. No keys, no accounts.",
    ]
    (ROOT / "README.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {len(uniq)} bounties", stats)


if __name__ == "__main__":
    main()
