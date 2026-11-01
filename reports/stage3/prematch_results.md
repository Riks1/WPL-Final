# Stage 3 pre-match evaluation (D11)

Note: tag `prereg-s3` (308c096b556c) does not contain the pre-registration documents; first committed: e39e0a3e259009f6bbf5363efd10a7699c89b41d 2026-11-01T17:11:07+00:00. See the model card.

Snapshot `all_female_json_20261025b.zip`; ratings `1e5c4bd424cfdd6b…`; h = 4.0.

**Verdict: serve `base_rate`** - primary vs base rate +0.0868 [+0.0123, +0.1620]; deploy iff the upper bound < 0.

## Women's Premier League (66 test matches)

| model     |   log_loss |   ci_low |   ci_high |   delta |   delta_ci_low |   delta_ci_high |   brier |    ece |   cal_slope |   cal_intercept |   accuracy |
|:----------|-----------:|---------:|----------:|--------:|---------------:|----------------:|--------:|-------:|------------:|----------------:|-----------:|
| base_rate |     0.7027 |   0.6327 |    0.7702 |  0      |         0      |          0      |  0.254  | 0.1162 |     -1.7055 |          0.234  |     0.5758 |
| primary   |     0.7895 |   0.681  |    0.9009 |  0.0868 |         0.0123 |          0.162  |  0.2825 | 0.1729 |     -0.7918 |          0.1894 |     0.5303 |
| s1        |     0.8256 |   0.7094 |    0.9417 |  0.1229 |         0.0548 |          0.1966 |  0.3004 | 0.1979 |     -1.457  |          0.2614 |     0.5303 |
| s2        |     0.7904 |   0.6821 |    0.9031 |  0.0877 |         0.014  |          0.1624 |  0.2832 | 0.1308 |     -0.8115 |          0.1873 |     0.5303 |

primary - base_rate log-loss: +0.0868 [+0.0123, +0.1620]

## T20I India (53 test matches) - supporting only, never decides

| model     |   log_loss |   ci_low |   ci_high |   delta |   delta_ci_low |   delta_ci_high |   brier |    ece |   cal_slope |   cal_intercept |   accuracy |
|:----------|-----------:|---------:|----------:|--------:|---------------:|----------------:|--------:|-------:|------------:|----------------:|-----------:|
| base_rate |     0.6936 |   0.6809 |    0.7063 |  0      |         0      |          0      |  0.2502 | 0.0145 |    -16.1242 |          0.0581 |     0.5094 |
| primary   |     0.491  |   0.3804 |    0.6114 | -0.2025 |        -0.3115 |         -0.0787 |  0.1663 | 0.1644 |      1.1482 |          0.0347 |     0.717  |
| s1        |     0.5098 |   0.3934 |    0.6427 | -0.1837 |        -0.3018 |         -0.0496 |  0.1723 | 0.1274 |      1.0464 |         -0.1131 |     0.717  |
| s2        |     0.4927 |   0.3866 |    0.6072 | -0.2008 |        -0.3056 |         -0.0849 |  0.1645 | 0.1333 |      1.259  |          0.017  |     0.6981 |

primary - base_rate log-loss: -0.2025 [-0.3115, -0.0787]
