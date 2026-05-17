"""Banner Personalization Agent — Google ADK (workshop build)."""

import os
import datetime
import requests
from datetime import timezone
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from banner_agent.image_agent import banner_image_agent

ODDS_API_KEY = os.environ["ODDS_API_KEY"]
ODDS_BASE = "https://api.the-odds-api.com/v4"
ORCHESTRATOR_MODEL = os.environ.get("ORCHESTRATOR_MODEL", "gemini-2.5-flash")
OLLAMA_API_BASE = os.environ.get("OLLAMA_API_BASE", "")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "ollama/gemma3:27b")
USE_GEMMA = bool(OLLAMA_API_BASE)

if USE_GEMMA:
    os.environ.setdefault("OLLAMA_API_BASE", OLLAMA_API_BASE)

def _resolve_orchestrator_model():
    """Gemma on Ollama (GCP) or Gemini Flash for planning and tool calls."""
    if USE_GEMMA:
        from google.adk.models import Gemma3Ollama

        return Gemma3Ollama(model=OLLAMA_MODEL)
    return ORCHESTRATOR_MODEL



def get_upcoming_matches(league_key: str) -> dict:
    """
    Returns the next 10 upcoming matches for the given league.

    Args:
        league_key: The Odds API sport key, e.g. 'soccer_spain_la_liga'.

    Returns:
        Dict with 'matches' list (event_id, home_team, away_team,
        commence_time) and 'credits_remaining'.
    """
    response = requests.get(
        f"{ODDS_BASE}/sports/{league_key}/events/",
        params={"apiKey": ODDS_API_KEY, "dateFormat": "iso"},
        timeout=10,
    )
    if response.status_code != 200:
        return {"error": f"API error {response.status_code}", "detail": response.text}

    now = datetime.datetime.now(timezone.utc).isoformat()
    events = response.json()
    upcoming = sorted(
        [e for e in events if e["commence_time"] >= now],
        key=lambda e: e["commence_time"],
    )[:10]

    return {
        "league_key": league_key,
        "credits_remaining": response.headers.get("x-requests-remaining", "?"),
        "matches": [
            {
                "event_id": e["id"],
                "home_team": e["home_team"],
                "away_team": e["away_team"],
                "commence_time": e["commence_time"],
            }
            for e in upcoming
        ],
    }

def get_match_odds(league_key: str, event_id: str) -> dict:
    """
    Returns decimal 1X2 odds from the first available EU bookmaker
    for a specific match.

    Args:
        league_key: Same sport key used in get_upcoming_matches.
        event_id:   UUID from get_upcoming_matches output.

    Returns:
        Dict with home/away/draw decimal odds, bookmaker name,
        match teams, kick-off time, and credits_remaining.
    """
    response = requests.get(
        f"{ODDS_BASE}/sports/{league_key}/odds/",
        params={
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal",
            "eventIds": event_id,
            "dateFormat": "iso",
        },
        timeout=10,
    )
    if response.status_code != 200:
        return {"error": f"API error {response.status_code}", "detail": response.text}

    events = response.json()
    if not events:
        return {"error": "No odds found for this event_id / league combination."}

    event = events[0]
    bookmakers = event.get("bookmakers", [])
    if not bookmakers:
        return {"error": "No EU bookmakers returned odds for this event."}

    bookie = bookmakers[0]
    markets = {m["key"]: m for m in bookie["markets"]}
    outcomes = {o["name"]: o["price"] for o in markets.get("h2h", {}).get("outcomes", [])}

    return {
        "event_id": event_id,
        "home_team": event["home_team"],
        "away_team": event["away_team"],
        "commence_time": event["commence_time"],
        "bookmaker": bookie["title"],
        "odds": {
            "home": outcomes.get(event["home_team"]),
            "away": outcomes.get(event["away_team"]),
            "draw": outcomes.get("Draw"),
        },
        "credits_remaining": response.headers.get("x-requests-remaining", "?"),
    }

WMO_PHRASES = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 61: "light rain", 63: "rainy", 65: "heavy rain",
    80: "rain showers", 95: "thunderstorms",
}


def get_weather(city: str) -> dict:
    """
    Returns current weather for a city as a banner-ready phrase.

    Args:
        city: Match host city, e.g. 'Manchester', 'Madrid', 'Milan'.

    Returns:
        Dict with 'phrase' (e.g. 'rainy in Madrid'), 'temperature_c',
        'condition', and 'city'.
    """
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    results = geo.json().get("results")
    if not results:
        return {"error": f"City not found: {city}"}

    lat, lon = results[0]["latitude"], results[0]["longitude"]
    wx = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weathercode",
            "timezone": "auto",
        },
        timeout=10,
    )
    current = wx.json().get("current", {})
    code = current.get("weathercode", 0)
    temp = current.get("temperature_2m")
    condition = WMO_PHRASES.get(code, "pleasant weather")
    phrase = f"{condition} in {city}"

    return {
        "city": city,
        "phrase": phrase,
        "temperature_c": temp,
        "condition": condition,
    }
  
_ORCHESTRATOR_LABEL = (
    f"Gemma 3 ({OLLAMA_MODEL}) + Nano Banana sub-agent"
    if USE_GEMMA
    else f"{ORCHESTRATOR_MODEL} + Nano Banana sub-agent"
)
root_agent = Agent(
    name="banner_personalization_agent",
    description=f"Promotional banner generator for iGaming offers. {_ORCHESTRATOR_LABEL}",
    model=_resolve_orchestrator_model(),
    tools=[
      get_upcoming_matches,
      get_match_odds,
      get_weather,
      AgentTool(banner_image_agent)
    ],
    sub_agents=[banner_image_agent],
    instruction="""
You are a promotional banner generator for an iGaming platform.

For each offer (bonus_code, bonus_amount, sport):
1. Resolve league (football: soccer_epl, soccer_spain_la_liga, …).
2. get_upcoming_matches → pick soonest match.
3. get_match_odds for decimal odds.
4. Infer host city from home_team; get_weather(city).
5. Pick one skyline landmark for that city.
6. Call banner_image_agent with home_team, away_team, kickoff_display,
   odds_home, odds_away, odds_draw (football only), bonus_code, bonus_amount,
   weather_phrase, skyline_landmark.
7. Reply with a short text summary (no file paths).

Never skip odds or weather.
Never use pictures of players who don't play anymore in this team.
Always use pictures of jerseys and other characteristics on the current setup of the teams.
""",
)