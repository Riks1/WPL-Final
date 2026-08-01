from flask import Blueprint, current_app, jsonify

from app.errors import InvalidInputError
from app.services import live as live_service

cricapi_bp = Blueprint("cricapi", __name__, url_prefix="/api")


@cricapi_bp.route("/cricapi-live/<match_id>")
def cricapi_live(match_id):
    import requests

    api_key = current_app.config.get("CRICAPI_KEY")
    if not api_key:
        raise InvalidInputError(
            "CRICAPI_KEY not set. Copy .env.example to .env and add your own key."
        )

    url = f"https://api.cricapi.com/v1/match_info?apikey={api_key}&id={match_id}"
    resp = requests.get(url, timeout=10)
    api_data = resp.json()

    if api_data.get("status") != "success":
        raise InvalidInputError(f"CricAPI error: {api_data.get('status', 'unknown error')}")

    match_data = api_data["data"]
    score_data = match_data.get("score", [])
    if not score_data:
        raise InvalidInputError("No score data available. Match may not have started yet.")

    current_innings = score_data[-1]
    innings_num = len(score_data)
    runs = current_innings.get("r", 0)
    wickets = current_innings.get("w", 0)
    overs = current_innings.get("o", 0)
    balls_faced = int(overs * 6)

    target = 0
    if innings_num == 2 and len(score_data) > 1:
        target = score_data[0].get("r", 0) + 1

    raw = {
        "innings": innings_num,
        "cum_runs": runs,
        "cum_wickets": wickets,
        "balls_faced": balls_faced,
        "target": target,
    }
    result = live_service.predict(raw)
    result["success"] = True
    result["match_info"] = {
        "teams": match_data.get("teams", []),
        "venue": match_data.get("venue", ""),
        "status": match_data.get("status", ""),
        "current_score": f"{runs}/{wickets} ({overs} ov)",
    }
    return jsonify(result)
