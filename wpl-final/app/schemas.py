from marshmallow import Schema, fields, validate


class PrematchInputSchema(Schema):
    win_rate_diff = fields.Float(load_default=0.0)
    win_rate_diff_10 = fields.Float(load_default=0.0)
    venue_win_rate_diff = fields.Float(load_default=0.0)
    h2h_win_rate_diff = fields.Float(load_default=0.0)
    venue_exp = fields.Float(load_default=0.0)
    toss_won_by_A = fields.Integer(load_default=0, validate=validate.OneOf([0, 1]))
    toss_choice = fields.Integer(load_default=0, validate=validate.OneOf([0, 1]))


class LiveInputSchema(Schema):
    innings = fields.Integer(load_default=2, validate=validate.OneOf([1, 2]))
    cum_runs = fields.Integer(load_default=0, validate=validate.Range(min=0))
    cum_wickets = fields.Integer(load_default=0, validate=validate.Range(min=0, max=10))
    balls_faced = fields.Integer(load_default=0, validate=validate.Range(min=0, max=120))
    target = fields.Integer(load_default=0, validate=validate.Range(min=0))
    runs_last_6_overs = fields.Integer(load_default=48, validate=validate.Range(min=0))
    last_6_overs_rr = fields.Float(load_default=8.0, validate=validate.Range(min=0))
