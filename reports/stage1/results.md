# Stage 1 results

Snapshot `wpl_json_20261025.zip` (sha256 `533e7937056b47f1…`): 88 matches. Folds: train [2023] → test 2024; train [2023, 2024] → test 2025; train [2023, 2024, 2025] → test 2026. Test set: 66 matches, 15643 ball rows. 95% CIs: percentile bootstrap over matches, 2000 resamples, paired across models.

Label: P(team batting first wins); super-over ties count for the super-over winner. Team batting first won 7/22 (2023), 11/22 (2024), 7/22 (2025), 10/22 (2026); chi-square test of equal rates: χ² = 2.42, df = 3, p = 0.490.

## Live models (both innings, held-out seasons)

| Model                                                 | Log-loss per match [95% CI]   | Δ vs base rate [95% CI]   | Brier per match [95% CI]   | Log-loss per ball [95% CI]   |   ECE |
|:------------------------------------------------------|:------------------------------|:--------------------------|:---------------------------|:-----------------------------|------:|
| Base rate (constant)                                  | 0.703 [0.633, 0.770]          | 0.000 [0.000, 0.000]      | 0.254 [0.220, 0.286]       | 0.713 [0.642, 0.780]         | 0.127 |
| Par-score: DLS curve + negative binomial              | 0.528 [0.428, 0.633]          | -0.175 [-0.286, -0.059]   | 0.179 [0.143, 0.217]       | 0.539 [0.437, 0.644]         | 0.064 |
| Par-score: DLS curve + Poisson (reference)            | 0.663 [0.472, 0.874]          | -0.040 [-0.235, 0.178]    | 0.190 [0.146, 0.237]       | 0.679 [0.484, 0.893]         | 0.107 |
| Par-score: polynomial + negative binomial (reference) | 0.527 [0.427, 0.633]          | -0.175 [-0.286, -0.061]   | 0.178 [0.142, 0.217]       | 0.538 [0.436, 0.644]         | 0.063 |
| Logistic, per innings                                 | 0.575 [0.453, 0.717]          | -0.128 [-0.243, 0.002]    | 0.190 [0.151, 0.233]       | 0.588 [0.463, 0.733]         | 0.079 |
| Random forest, per innings                            | 0.652 [0.512, 0.814]          | -0.050 [-0.185, 0.101]    | 0.208 [0.169, 0.253]       | 0.667 [0.524, 0.830]         | 0.108 |

## Per innings and phase (log-loss per ball [95% CI])

|   Innings | Phase     |   Matches |   Rows | base_rate            | parscore             | logistic             | rf                   |
|----------:|:----------|----------:|-------:|:---------------------|:---------------------|:---------------------|:---------------------|
|         1 | powerplay |        66 |   2494 | 0.705 [0.635, 0.773] | 0.697 [0.621, 0.773] | 0.748 [0.657, 0.845] | 0.814 [0.700, 0.942] |
|         1 | middle    |        66 |   4072 | 0.703 [0.633, 0.771] | 0.628 [0.514, 0.744] | 0.678 [0.538, 0.841] | 0.813 [0.618, 1.045] |
|         1 | death     |        66 |   1611 | 0.707 [0.638, 0.773] | 0.592 [0.451, 0.749] | 0.744 [0.505, 1.010] | 0.731 [0.523, 0.970] |
|         2 | powerplay |        66 |   2464 | 0.703 [0.633, 0.770] | 0.510 [0.369, 0.664] | 0.523 [0.365, 0.690] | 0.600 [0.410, 0.806] |
|         2 | middle    |        66 |   3953 | 0.712 [0.642, 0.779] | 0.373 [0.225, 0.529] | 0.395 [0.253, 0.559] | 0.482 [0.301, 0.695] |
|         2 | death     |        53 |   1049 | 0.812 [0.728, 0.889] | 0.429 [0.202, 0.720] | 0.496 [0.289, 0.724] | 0.501 [0.322, 0.701] |

## Calibration sensitivity (44 matches; calibrators fitted on earlier seasons only; not deployed)

| Model                | Log-loss per match [95% CI]   | Δ vs uncalibrated [95% CI]   |
|:---------------------|:------------------------------|:-----------------------------|
| logistic             | 0.483 [0.405, 0.564]          | 0.000 [0.000, 0.000]         |
| logistic+platt       | 0.635 [0.532, 0.737]          | 0.152 [0.072, 0.236]         |
| logistic+temperature | 0.532 [0.495, 0.570]          | 0.049 [0.003, 0.095]         |
| logistic+isotonic    | 0.661 [0.551, 0.781]          | 0.178 [0.089, 0.273]         |
| rf                   | 0.549 [0.450, 0.666]          | 0.000 [0.000, 0.000]         |
| rf+platt             | 0.647 [0.544, 0.760]          | 0.097 [0.020, 0.174]         |
| rf+temperature       | 0.554 [0.508, 0.602]          | 0.005 [-0.066, 0.065]        |
| rf+isotonic          | 0.683 [0.554, 0.844]          | 0.134 [0.043, 0.231]         |
| parscore             | 0.515 [0.420, 0.623]          | 0.000 [0.000, 0.000]         |
| parscore+platt       | 0.576 [0.470, 0.686]          | 0.060 [0.006, 0.116]         |
| parscore+temperature | 0.519 [0.453, 0.595]          | 0.004 [-0.031, 0.037]        |
| parscore+isotonic    | 0.597 [0.482, 0.717]          | 0.082 [0.023, 0.144]         |

## Pre-match model (post-toss)

| Model                                         | Log-loss [95% CI]    | Δ vs base rate [95% CI]   |   Accuracy |
|:----------------------------------------------|:---------------------|:--------------------------|-----------:|
| Base rate                                     | 0.703 [0.633, 0.770] | 0.000 [0.000, 0.000]      |      0.576 |
| Pre-match logistic (form, head-to-head, toss) | 0.769 [0.673, 0.872] | 0.066 [0.001, 0.135]      |      0.515 |

## Deployment decision

- Rule: `parscore_baseline`.
- logistic − parscore: +0.0469 [-0.0229, +0.1177]
- rf − parscore: +0.1244 [+0.0453, +0.2079]
- → live model deployed: **parscore**.
- Pre-match: logistic − base rate +0.0659 [+0.0014, +0.1353] → serve **base_rate**.


