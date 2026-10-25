from marshmallow import EXCLUDE, Schema, ValidationError, fields, validate, validates_schema


class PrematchInputSchema(Schema):
    """After the toss, before ball 1. Team names must be ones the model has history for."""

    class Meta:
        unknown = EXCLUDE

    bat_first_team = fields.String(required=True, validate=validate.Length(min=1))
    chase_team = fields.String(required=True, validate=validate.Length(min=1))
    toss_winner = fields.String(required=True, validate=validate.Length(min=1))

    @validates_schema
    def check_teams(self, data, **kwargs):
        if data["bat_first_team"] == data["chase_team"]:
            raise ValidationError("must differ from bat_first_team", "chase_team")
        if data["toss_winner"] not in (data["bat_first_team"], data["chase_team"]):
            raise ValidationError("must be bat_first_team or chase_team", "toss_winner")


class DeliverySchema(Schema):
    """One delivery of the current innings, in bowling order."""

    class Meta:
        unknown = EXCLUDE

    runs = fields.Integer(required=True, validate=validate.Range(min=0, max=12))      # total incl. extras
    legal = fields.Boolean(load_default=True)                                        # False for wide / no-ball
    wickets = fields.Integer(load_default=0, validate=validate.Range(min=0, max=2))   # retired hurt = 0


class LiveInputSchema(Schema):
    """Ball history of the current innings. The server derives every feature from it with
    the same function the training notebook uses (wpl/live_features.py)."""

    class Meta:
        unknown = EXCLUDE

    innings = fields.Integer(required=True, validate=validate.OneOf([1, 2]))
    balls = fields.List(fields.Nested(DeliverySchema), required=True, validate=validate.Length(max=400))
    target = fields.Integer(load_default=None, allow_none=True, validate=validate.Range(min=1, max=400))
    max_balls = fields.Integer(load_default=120, validate=validate.Range(min=6, max=120))

    @validates_schema
    def check_state(self, data, **kwargs):
        if data["innings"] == 2 and data.get("target") is None:
            raise ValidationError("required in innings 2", "target")
        legal = sum(1 for b in data["balls"] if b["legal"])
        if legal > data["max_balls"]:
            raise ValidationError(f"{legal} legal balls exceeds max_balls={data['max_balls']}", "balls")
        if sum(b["wickets"] for b in data["balls"]) > 10:
            raise ValidationError("more than 10 wickets", "balls")
