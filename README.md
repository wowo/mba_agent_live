# MBA Agent Live

A Google ADK agent that builds personalized iGaming promotional banners: it pulls upcoming matches and decimal odds from [The Odds API](https://the-odds-api.com/), adds local weather for the host city, then delegates to a Gemini image sub-agent to render a 16:9 banner with teams, kickoff, odds, bonus offer, weather, and a skyline landmark. Run it with `adk web` and provide a bonus code, amount, and sport to generate a banner for the next relevant fixture.

The orchestrator can run on **Google Gemini** (default) or on a **Gemma 3** model served locally via **Ollama** — set `OLLAMA_API_BASE` in `.env` to switch. Banner image generation still uses Gemini either way. You can also wire in any other model you prefer by changing `_resolve_orchestrator_model()` in `banner_agent/agent.py` (and the `model=` on `banner_image_agent` in `banner_agent/image_agent.py` for the image step).

## Setup

Requires **Python 3.10+**.

```bash
cd mba_agent_live
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.dist .env
# Edit .env with your API keys (see below)
```

## API keys

Copy `.env.dist` to `.env` and set:

| Variable | Where to get it |
|----------|-----------------|
| `ODDS_API_KEY` | Sign up at [the-odds-api.com](https://the-odds-api.com/) and copy your API key from the dashboard. |
| `GOOGLE_API_KEY` | Create a key in [Google AI Studio](https://aistudio.google.com/apikey) (required for banner images; also used by the Gemini orchestrator unless you use Ollama). |

For **Ollama / Gemma 3**, also set `OLLAMA_API_BASE` (e.g. `http://localhost:11434`) and optionally `OLLAMA_MODEL` (default `ollama/gemma3:27b`). Install [Ollama](https://ollama.com/) and pull the model before starting the agent.

## Run with ADK Web

From the **repository root** (the directory that contains `banner_agent/`), with the virtualenv activated:

```bash
adk web
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. ADK discovers the `banner_agent` app automatically (`root_agent` in `banner_agent/agent.py`). Start a new chat session and send a prompt with the offer details, for example:

> Create a football banner: bonus code BONUS10, 100% up to $100, La Liga.

The agent fetches the next match, odds, and weather, then generates a banner image shown in the session (artifacts are stored under `.adk/artifacts/`).
