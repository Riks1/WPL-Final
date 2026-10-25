from flask import Blueprint

from app.errors import AppError

cricapi_bp = Blueprint("cricapi", __name__, url_prefix="/api")


@cricapi_bp.route("/cricapi-live/<match_id>")
def cricapi_live(match_id):
    # The v1 live model needs the ball history of the innings (recent runs, recent wickets,
    # partnership). CricAPI's match_info returns only score totals, so this route cannot
    # produce a valid input. Re-enabling it with a ball-by-ball feed is a stage 9 decision.
    raise AppError("Disabled in v1: the live model needs ball-by-ball history, which CricAPI match_info "
                   "does not provide. POST the ball history to /api/live-predict instead.", status_code=501)
