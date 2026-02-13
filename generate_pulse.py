#!/usr/bin/env python3
"""
Robotics Pulse — Automated bi-weekly robotics industry intelligence report.

Fetches RSS feeds from top robotics sources, synthesizes them through
Claude API, and writes a structured markdown report.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python generate_pulse.py
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
import feedparser
import requests
import yaml


SCRIPT_DIR = Path(__file__).parent


def load_config():
    """Load feed URLs and settings from config.yml."""
    config_path = SCRIPT_DIR / "config.yml"
    if not config_path.exists():
        print("❌ config.yml not found")
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def parse_entry_date(entry):
    """Extract datetime from a feedparser entry, return None if unparseable."""
    for date_field in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, date_field, None)
        if parsed:
            try:
                return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue
    return None


def fetch_feed(url, name, max_articles):
    """Fetch and parse a single RSS feed. Returns list of article dicts."""
    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={"User-Agent": "RoboticsPulse/1.0"},
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠️  {name}: fetch failed — {e}")
        return []

    feed = feedparser.parse(resp.text)
    if not feed.entries:
        print(f"  ⚠️  {name}: no entries found")
        return []

    articles = []
    for entry in feed.entries[:max_articles]:
        articles.append({
            "title": entry.get("title", "Untitled"),
            "description": (entry.get("summary") or entry.get("description") or "")[:500],
            "link": entry.get("link", ""),
            "date": parse_entry_date(entry),
            "source": name,
        })

    print(f"  ✅ {name}: {len(articles)} articles")
    return articles


def fetch_all_feeds(config):
    """Fetch all configured feeds. Returns (general_articles, figure_articles)."""
    print("Fetching feeds...")
    general = []
    figure = []
    settings = config["settings"]

    for feed_cfg in config["feeds"]:
        articles = fetch_feed(
            feed_cfg["url"],
            feed_cfg["name"],
            settings["max_articles_per_feed"],
        )
        if feed_cfg.get("tag") == "figure_watch":
            figure.extend(articles)
        else:
            general.extend(articles)

    print(f"\n📊 Total: {len(general)} general + {len(figure)} Figure AI articles")
    return general, figure


def filter_by_date(articles, days):
    """Filter articles to the lookback window. Includes undated articles."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = [a for a in articles if a["date"] is None or a["date"] >= cutoff]
    filtered.sort(key=lambda a: a["date"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return filtered


def format_articles_for_prompt(articles):
    """Format article list into a text block for the Claude prompt."""
    if not articles:
        return "(No articles available)"

    blocks = []
    for a in articles:
        date_str = a["date"].strftime("%Y-%m-%d") if a["date"] else "Unknown"
        blocks.append(
            f"[Source: {a['source']}] [Date: {date_str}]\n"
            f"Title: {a['title']}\n"
            f"Description: {a['description']}\n"
            f"Link: {a['link']}\n"
            f"---"
        )
    return "\n".join(blocks)


def build_date_range(days):
    """Build a human-readable date range string."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"


def synthesize_report(general_text, figure_text, date_range, config):
    """Send articles to Claude API and get the synthesized report."""
    prompt = f"""You are a concise robotics industry analyst writing a bi-weekly briefing
for a busy tech entrepreneur. Your reader builds AI agent systems and
follows robotics as a strategic interest — they want signal, not noise.

Below are articles from the past two weeks gathered from robotics RSS
feeds. Synthesize them into the report format specified below. Be
opinionated about what matters most. Keep the total report to a 3-5
minute read.

ARTICLES:
{general_text}

FIGURE AI ARTICLES (for the Figure Watch section):
{figure_text}

Write the report in this exact markdown format:

# Robotics Pulse — {date_range}

## Top Signal
[One paragraph (3-4 sentences) about the single most significant
development from the articles above. Explain why it matters for the
industry. Be specific and cite the source.]

## Developments
[3-5 items, each formatted exactly as:]
- **[Headline]** — [2 sentences: what happened + why it matters.
  Include the source name in parentheses.]

## Figure Watch
[1-2 sentences about Figure AI news from the Figure AI articles above.
If no Figure AI articles were provided or none are significant, write
"No significant Figure AI news this cycle."]

## Trend Line
[One sentence identifying where momentum is shifting across these
developments. Connect dots between stories when possible.]

## Sources
[Numbered list of all referenced articles as markdown links]

RULES:
- Never invent or hallucinate information not in the provided articles
- If the same story appears from multiple sources, consolidate into one
  entry and cite all sources
- If fewer than 3 articles total, note the quiet period and work with
  what you have
- Prefer developments with concrete milestones (funding, product
  launches, partnerships, demos) over opinion pieces
- Keep language direct and jargon-light
- The Top Signal should be something the reader would want to text a
  colleague about"""

    settings = config["settings"]
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=settings["model"],
        max_tokens=settings["max_tokens"],
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def save_report(report_md, report_dir):
    """Write the report markdown to a dated file."""
    dir_path = SCRIPT_DIR / report_dir
    dir_path.mkdir(exist_ok=True)
    filename = f"{datetime.now().strftime('%Y-%m-%d')}-robotics-pulse.md"
    file_path = dir_path / filename
    file_path.write_text(report_md)
    print(f"\n📝 Report saved: {file_path}")
    return file_path


def main():
    """Orchestrate the full pipeline: fetch, filter, synthesize, save."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set")
        sys.exit(1)

    config = load_config()
    settings = config["settings"]

    general, figure = fetch_all_feeds(config)

    general = filter_by_date(general, settings["lookback_days"])
    figure = filter_by_date(figure, settings["lookback_days"])

    total = len(general) + len(figure)
    if total < 1:
        print("\n⚠️  No articles found in the lookback window. Quiet period — skipping report.")
        return

    print(f"\n🔬 After filtering: {len(general)} general + {len(figure)} Figure AI")

    general_text = format_articles_for_prompt(general)
    figure_text = format_articles_for_prompt(figure)
    date_range = build_date_range(settings["lookback_days"])

    print("\n🤖 Synthesizing report via Claude...")
    report_md = synthesize_report(general_text, figure_text, date_range, config)

    save_report(report_md, settings["report_dir"])
    print("✅ Done!")


if __name__ == "__main__":
    main()
