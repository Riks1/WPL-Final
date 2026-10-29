# Stage 3 ratings validation report (D10)

Snapshot `all_female_json_20261025b.zip`; ratings content hash `1e5c4bd424cfdd6b…`; h = 4.0; λ = 18.99. No metric here uses match results (PREREG §8).

## Batting-position shares (pre-2024)

1: 0.170, 2: 0.159, 3: 0.149, 4: 0.129, 5: 0.100, 6: 0.079, 7: 0.061, 8: 0.050, 9: 0.041, 10: 0.034, 11: 0.026

## Coverage: share of XI slots with ≥60 legal balls faced or bowled before the match; debutant share

| competition            |   season |   cov |   debut |
|:-----------------------|---------:|------:|--------:|
| T20I India             |     2009 | 0     |   1     |
| T20I India             |     2010 | 0     |   0.273 |
| T20I India             |     2011 | 0.045 |   0.318 |
| T20I India             |     2012 | 0.562 |   0.08  |
| T20I India             |     2014 | 0.664 |   0.1   |
| T20I India             |     2016 | 0.76  |   0.045 |
| T20I India             |     2018 | 0.862 |   0.031 |
| T20I India             |     2019 | 0.894 |   0.024 |
| T20I India             |     2020 | 0.982 |   0.009 |
| T20I India             |     2021 | 0.904 |   0.04  |
| T20I India             |     2022 | 0.966 |   0.002 |
| T20I India             |     2023 | 0.939 |   0.01  |
| T20I India             |     2024 | 0.965 |   0.004 |
| T20I India             |     2025 | 0.918 |   0.014 |
| T20I India             |     2026 | 0.988 |   0     |
| Women's Premier League |     2023 | 0.814 |   0.05  |
| Women's Premier League |     2024 | 0.878 |   0.021 |
| Women's Premier League |     2025 | 0.86  |   0.021 |
| Women's Premier League |     2026 | 0.932 |   0.029 |
| Women's T20 Challenge  |     2018 | 0.885 |   0.038 |
| Women's T20 Challenge  |     2019 | 0.807 |   0.068 |
| Women's T20 Challenge  |     2020 | 0.943 |   0.023 |
| Women's T20 Challenge  |     2022 | 0.864 |   0.068 |

## xi_margin (runs) by competition and season

| competition            |   season |   mean |    std |   count |
|:-----------------------|---------:|-------:|-------:|--------:|
| T20I India             |     2009 |   0    | nan    |       1 |
| T20I India             |     2010 |  -7    | nan    |       1 |
| T20I India             |     2011 |  -6.93 | nan    |       1 |
| T20I India             |     2012 | -10.47 |  15.43 |       8 |
| T20I India             |     2014 |  -1.67 |  12.16 |       5 |
| T20I India             |     2016 |   9.56 |  17.34 |       7 |
| T20I India             |     2018 |  -3.28 |  25.09 |      22 |
| T20I India             |     2019 |  -0.55 |  22.84 |      15 |
| T20I India             |     2020 |  -2.38 |  22.59 |      10 |
| T20I India             |     2021 |  -2.11 |   7.84 |       9 |
| T20I India             |     2022 |   1.3  |  21.68 |      20 |
| T20I India             |     2023 |   3.27 |  21.23 |      18 |
| T20I India             |     2024 |  -1.56 |  31.06 |      21 |
| T20I India             |     2025 |  -4.92 |  23.79 |      10 |
| T20I India             |     2026 |   3.37 |  23.73 |      23 |
| Women's Premier League |     2023 |  -3.47 |  13.24 |      22 |
| Women's Premier League |     2024 |  -1.34 |   7.2  |      22 |
| Women's Premier League |     2025 |  -5.76 |  17.51 |      22 |
| Women's Premier League |     2026 |  -0.74 |  10.23 |      22 |
| Women's T20 Challenge  |     2018 | -14.37 | nan    |       1 |
| Women's T20 Challenge  |     2019 |   0.15 |   2.75 |       4 |
| Women's T20 Challenge  |     2020 |  -1.22 |  10.83 |       4 |
| Women's T20 Challenge  |     2022 |   2.74 |   1.4  |       4 |

## Season-to-season rank stability (players with ≥100 effective balls in both)

|   from |   to | component   |   players |   spearman |
|-------:|-----:|:------------|----------:|-----------:|
|   2023 | 2024 | bat_runs    |        36 |      0.889 |
|   2023 | 2024 | bowl_runs   |        30 |      0.865 |
|   2024 | 2025 | bat_runs    |        33 |      0.949 |
|   2024 | 2025 | bowl_runs   |        31 |      0.779 |
|   2025 | 2026 | bat_runs    |        33 |      0.97  |
|   2025 | 2026 | bowl_runs   |        28 |      0.909 |

## Face validity: top 10 WPL players by season-end rating (≥100 effective balls)

|   season | list                   | player           |   rating |
|---------:|:-----------------------|:-----------------|---------:|
|     2023 | batting runs (top)     | L Harris         |    0.484 |
|     2023 | batting runs (top)     | Shafali Verma    |    0.256 |
|     2023 | batting runs (top)     | AJ Healy         |    0.252 |
|     2023 | batting runs (top)     | S Mandhana       |    0.24  |
|     2023 | batting runs (top)     | SFM Devine       |    0.226 |
|     2023 | batting runs (top)     | A Capsey         |    0.207 |
|     2023 | batting runs (top)     | GM Harris        |    0.189 |
|     2023 | batting runs (top)     | SIR Dunkley      |    0.181 |
|     2023 | batting runs (top)     | BL Mooney        |    0.161 |
|     2023 | batting runs (top)     | A Gardner        |    0.153 |
|     2023 | bowling economy (best) | M Kapp           |   -0.143 |
|     2023 | bowling economy (best) | S Ecclestone     |   -0.134 |
|     2023 | bowling economy (best) | S Ismail         |   -0.088 |
|     2023 | bowling economy (best) | S Ishaque        |   -0.077 |
|     2023 | bowling economy (best) | AC Kerr          |   -0.071 |
|     2023 | bowling economy (best) | ML Schutt        |   -0.065 |
|     2023 | bowling economy (best) | KJ Garth         |   -0.05  |
|     2023 | bowling economy (best) | S Pandey         |   -0.043 |
|     2023 | bowling economy (best) | HK Matthews      |   -0.026 |
|     2023 | bowling economy (best) | IECM Wong        |   -0.023 |
|     2024 | batting runs (top)     | GM Harris        |    0.268 |
|     2024 | batting runs (top)     | Shafali Verma    |    0.259 |
|     2024 | batting runs (top)     | AJ Healy         |    0.248 |
|     2024 | batting runs (top)     | SFM Devine       |    0.229 |
|     2024 | batting runs (top)     | S Mandhana       |    0.198 |
|     2024 | batting runs (top)     | BL Mooney        |    0.173 |
|     2024 | batting runs (top)     | LMM Tahuhu       |    0.148 |
|     2024 | batting runs (top)     | AC Jayangani     |    0.142 |
|     2024 | batting runs (top)     | RM Ghosh         |    0.139 |
|     2024 | batting runs (top)     | G Wareham        |    0.138 |
|     2024 | bowling economy (best) | M Kapp           |   -0.138 |
|     2024 | bowling economy (best) | TR Sadhu         |   -0.134 |
|     2024 | bowling economy (best) | S Ecclestone     |   -0.132 |
|     2024 | bowling economy (best) | S Ismail         |   -0.117 |
|     2024 | bowling economy (best) | AC Kerr          |   -0.066 |
|     2024 | bowling economy (best) | Renuka Singh     |   -0.047 |
|     2024 | bowling economy (best) | LMM Tahuhu       |   -0.047 |
|     2024 | bowling economy (best) | DB Sharma        |   -0.044 |
|     2024 | bowling economy (best) | S Pandey         |   -0.038 |
|     2024 | bowling economy (best) | S Ishaque        |   -0.031 |
|     2025 | batting runs (top)     | DN Wyatt         |    0.271 |
|     2025 | batting runs (top)     | Shafali Verma    |    0.259 |
|     2025 | batting runs (top)     | GM Harris        |    0.238 |
|     2025 | batting runs (top)     | DJS Dottin       |    0.232 |
|     2025 | batting runs (top)     | RM Ghosh         |    0.232 |
|     2025 | batting runs (top)     | DR Gibson        |    0.2   |
|     2025 | batting runs (top)     | S Mandhana       |    0.196 |
|     2025 | batting runs (top)     | BL Mooney        |    0.18  |
|     2025 | batting runs (top)     | NR Sciver-Brunt  |    0.149 |
|     2025 | batting runs (top)     | HK Matthews      |    0.128 |
|     2025 | bowling economy (best) | KS Gautam        |   -0.18  |
|     2025 | bowling economy (best) | M Kapp           |   -0.159 |
|     2025 | bowling economy (best) | S Ismail         |   -0.126 |
|     2025 | bowling economy (best) | S Ecclestone     |   -0.114 |
|     2025 | bowling economy (best) | S Pandey         |   -0.072 |
|     2025 | bowling economy (best) | KJ Garth         |   -0.069 |
|     2025 | bowling economy (best) | TP Kanwar        |   -0.055 |
|     2025 | bowling economy (best) | Renuka Singh     |   -0.052 |
|     2025 | bowling economy (best) | G Voll           |   -0.05  |
|     2025 | bowling economy (best) | AC Kerr          |   -0.046 |
|     2026 | batting runs (top)     | DN Wyatt         |    0.275 |
|     2026 | batting runs (top)     | Shafali Verma    |    0.267 |
|     2026 | batting runs (top)     | GM Harris        |    0.264 |
|     2026 | batting runs (top)     | RM Ghosh         |    0.247 |
|     2026 | batting runs (top)     | L Lee            |    0.247 |
|     2026 | batting runs (top)     | S Mandhana       |    0.189 |
|     2026 | batting runs (top)     | DJS Dottin       |    0.189 |
|     2026 | batting runs (top)     | BL Mooney        |    0.18  |
|     2026 | batting runs (top)     | SFM Devine       |    0.178 |
|     2026 | batting runs (top)     | G Wareham        |    0.165 |
|     2026 | bowling economy (best) | M Kapp           |   -0.174 |
|     2026 | bowling economy (best) | S Ismail         |   -0.132 |
|     2026 | bowling economy (best) | S Ecclestone     |   -0.11  |
|     2026 | bowling economy (best) | Vaishnavi Sharma |   -0.085 |
|     2026 | bowling economy (best) | S Pandey         |   -0.073 |
|     2026 | bowling economy (best) | LK Hamilton      |   -0.067 |
|     2026 | bowling economy (best) | KS Gautam        |   -0.061 |
|     2026 | bowling economy (best) | NSS Sharma       |   -0.054 |
|     2026 | bowling economy (best) | LK Bell          |   -0.049 |
|     2026 | bowling economy (best) | Renuka Singh     |   -0.043 |
