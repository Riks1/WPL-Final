# RATINGS_SPEC v1.1 — as-of player ratings, venue priors, XI strength

Status: **v1.1, for approval** (v1 corrected while writing the builder; changes marked **[v1.1]**). It is tagged with `PREREG_stage3.md` as `prereg-s3`. It implements D-014 (ball-level, hierarchical shrinkage, adjusted for phase, venue, competition and match state) and the D-011 ratings scope. D-012's s_c is **not** used: it weights the model pool only.

## 1. Data
- **Snapshot:** `all_female_json_20261025b.zip`, through the Stage 2 tables.
- **Matches [v1.1]:** **all** parsed 20-over, 6-ball women's T20s, main innings only (no super overs). The `ratings_scope` flag is set from players' *whole* WPL careers, so filtering on it would pick matches using future information. Using every match avoids that, and gives the baselines and opponent ratings more data. The flag stays available as an option (`scope='ratings'`).
- **Exclusions:** those in `data/exclusions.json`.

## 2. Ball outcomes (four components)
| Component | Rows | Outcome |
|---|---|---|
| Batting runs | Deliveries with `ball_faced` | `runs_batter` |
| Batting dismissal | Deliveries with `ball_faced` | 1 if the striker is out (team dismissal, `player_out == batter`) |
| Bowling runs | All deliveries | `bowler_runs` |
| Bowling wicket | All deliveries | 1 if `bowler_credited` |

## 3. Context baseline (expected outcome per ball)
- **Cell** = (competition, phase {overs 1–6, 7–15, 16–20}, wickets lost {0–2, 3–5, 6+}, innings {1, 2}).
- **Cell value** = the as-of, time-decayed mean (section 6 decay), shrunk towards the pooled (phase, wickets, innings) cell, with prior strength `k_cell` balls. The pooled cell is shrunk towards the overall decayed mean with prior strength `k_pool` balls (section 9) **[v1.1]**.
- **First day [v1.1]:** on the first date with no earlier balls there is nothing to predict from. That day's balls update the baselines, but no player learns from them.
- This is where the competition offsets come from (D-014).

## 4. Venue effect
- **Venue run effect:** the as-of, time-decayed mean of the residual (outcome − cell value) for batting runs at the venue, shrunk towards 0 with prior strength `k_venue` balls.
- **Use [v1.1]:** added to the expected batting runs **and** to the expected bowling runs: a high-scoring ground raises the runs a bowler is expected to concede (v1 said "subtracted", which was wrong).

## 5. Opponent adjustment
- **Batting expectation for a ball:** cell value + venue effect + the bowler's matching as-of rating (bowling runs for batting runs; bowling wickets for batting dismissals).
- **Bowling expectation:** the mirror image, using the batter's matching as-of rating. Ratings are deviations from the cell average, so the opponent's rating is added as it is **[v1.1]**.
- Opponent ratings are as-of strictly earlier dates, so there's a single sequential pass and no iteration.

## 6. Rating update (empirical Bayes)
For each player and component:
- **Residual** r = outcome − expectation, on the probability scale for the two event components.
- **Rating [v1.1]** = (Σ wᵢ rᵢ + k · μ₀) / (Σ wᵢ + k), with wᵢ = 0.5^(ageᵢ / h): the posterior mean with prior mean μ₀ and prior strength k balls. Age is in years from the ball's date to the as-of date.
- **SD** = √(σ² / (Σ wᵢ + k)), with σ² the pooled residual variance of the component, estimated in pass 1 on pre-2024 balls **[v1.1]** (never from the full data).
- **k** = σ² / τ², where τ² is the between-player variance, estimated by method of moments on balls before 2024-01-01.
- **μ₀ (debutant prior)** = the mean residual over players' first 60 balls (faced or bowled) before 2024-01-01, per component. Every player starts there.

## 7. As-of rule
- Ratings for a match on date d use only deliveries dated **before** d. Same-day double-headers don't see each other.
- The build walks match dates in order.
- **Hindsight (full-data) ratings** go only into `ratings_hindsight` and are never joined into features.

## 8. Players and edge cases
- **Who is rated:** every player in ratings-scope matches. Opponents are needed for the adjustment; outputs focus on WPL players.
- **Retired hurt:** not a dismissal (D-005). Retired out counts as a team dismissal but isn't credited to the bowler (D-013).
- **Concussion substitutes:** their balls count for the player who faced or bowled them.
- **Switches:** ratings are player-level, with no team carry-over (D-014). `two_teams_in_season` cases are listed in the validation report.
- **Data-supported:** ≥60 legal balls faced (batting) or ≥60 legal balls bowled (bowling) before the match. Used for the coverage KPI only; the model itself has no cut-off.

## 9. Hyperparameters (fixed before the tag; balls before 2024-01-01 only)
- **h** (half-life, shared by cells, venues and ratings) ∈ {1, 2, 4, ∞} years. Chosen by one-step-ahead mean squared error of batting runs per ball on 2022–2023 ratings-scope balls, with each ball predicted from ratings as of its date.
- **`k_cell`** = 500 balls. **`k_venue`** = 1,000 balls.
- **`k_pool`** = 2,000 balls **[v1.1]**.
- **Two-pass procedure [v1.1]:** pass 1 on pre-2024 balls with μ₀ = 0, k = 100 and σ² = 1 gives the residuals. From those: μ₀ = the mean residual over each player's first 60 rows; σ² = the residual variance; k = σ² / τ², with τ² = (variance of player mean residuals, players with ≥30 rows) − mean(σ² / nᵢ). If τ² ≤ 0, k is capped at 10⁵ (no detectable player differences, so ratings stay at μ₀). Pass 2 uses these fixed values.
- **k per component:** by the method of moments above.
- **λ (runs value of a wicket)** = total runs ÷ total team dismissals over main innings in ratings-scope matches before 2024-01-01.

## 10. XI strength (per match and team)
1. **Toss XI** = team sheet minus recorded replacements' `in` players. The 13-player 2018 exhibition is flagged.
2. **Batting order:** rank the XI by as-of mean batting position. Players with no batting history go last, in team-sheet order. Rank → share of the team's balls faced at that position, from the pre-2024 average.
3. **Bowling shares:** as-of mean legal balls bowled per match, normalised to 120, each capped at 24 and renormalised. If fewer than 5 players have bowling history, the remaining balls are spread evenly over the next players in team-sheet order, at μ₀.
4. **Team batting value** = 120 × Σ shareᵢ × (bat_runsᵢ − λ · bat_dismissalᵢ).
5. **Team bowling value** = 120 × Σ shareⱼ × (λ · bowl_wicketⱼ − bowl_runsⱼ).
6. **`xi_margin`** = (bat + bowl) of the team batting first − (bat + bowl) of the chasing team, in runs.
7. Also stored: per-team uncertainty (120 · √Σ share² · SD²) and coverage (share of slots that are data-supported).

## 11. Venue bat-first prior (supersedes D-006's "no venue features")
`venue_bf_prior` = the as-of share of model-scope matches at the venue won by the team batting first, shrunk towards the model-scope pooled rate with a prior strength of 20 matches.

## 12. Determinism and versioning
- No randomness; every sort order is explicit.
- **Ratings version** = SHA-256 over the sorted rows of the ratings table, recorded in the build summary alongside the snapshot sha.

## 13. Known simplifications
- No chase-pressure state (required rate).
- No fielding or captaincy.
- Event components are linear on the probability scale.
- Indian domestic cricket is absent (D-011), so uncapped players rely on μ₀.
