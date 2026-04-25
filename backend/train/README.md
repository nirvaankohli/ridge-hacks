# Training

(For judges)

This folder trains a supervised solar-storm risk model from NASA DONKI data.

Current model:

- `XGBoost` multiclass classifier



Data used:

- `CMEAnalysis` for CME speed, direction, half-angle, and predicted shock arrivals
- `FLR` for recent flare counts and intensity bands
- `GST` for observed Kp labels

Target:

- Predict a latitude-specific local risk class:
  - `quiet`
  - `watch`
  - `moderate`
  - `high`
  - `severe`

Train:

```powershell
.\.venv\Scripts\python.exe -m train.train_model --start-date 2025-01-01 --end-date 2026-04-25
```

Predict:

```powershell
.\.venv\Scripts\python.exe -m train.predict_risk --latitude 45 --earth-directed-cme-count-72h 2 --max-cme-speed-72h 1400 --impact-count-24h 1 --x-flare-count-72h 1 --prior-day-max-kp 5
```

Time-based evaluation:

```powershell
.\.venv\Scripts\python.exe -m train.evaluate_time_split
```
