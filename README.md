# Robotics Pulse

Automated bi-weekly robotics industry intelligence report. Runs on GitHub Actions, fetches RSS feeds from top robotics sources, synthesizes through Claude API, and commits a structured markdown report.

## Reading Reports

Browse the [`reports/`](reports/) directory. Each file is a self-contained 3-5 minute briefing covering the most significant developments in robotics over the prior two weeks.

## Schedule

Runs automatically on the **1st and 15th of each month** at 9am ET. Can also be triggered manually from the [Actions tab](../../actions).

## Sources

| Source | Coverage |
|--------|----------|
| IEEE Spectrum Robotics | Gold standard robotics journalism |
| The Robot Report | Dedicated industry news |
| Robohub | Community + research perspectives |
| TechCrunch Robotics | Startup and funding activity |
| MIT Technology Review | High-quality AI/robotics coverage |
| Figure AI (via Google News) | Figure-specific press coverage |
| arXiv Robotics | Academic research papers |

## Adding or Removing Feeds

Edit `config.yml` — each feed is a one-liner with `name` and `url`. No code changes needed.

## Local Development

```bash
git clone git@github.com:robbyDAninja/robotics-pulse.git
cd robotics-pulse
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python generate_pulse.py
```

## Cost

~$0.003 per report (~$0.08/year) using Claude Haiku.
