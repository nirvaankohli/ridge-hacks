# Everything Tried

Things we tried to improve the 5-class solar storm model, but that did not solve the accuracy problem well enough:

- Oversampled minority classes after the train split.
- Widened the `moderate` and `high` label bands.
- Added more derived features from CME, flare, and geomagnetic history.
- Added NOAA-style history features like prior G-scale, storm-day counts, storm streak, and rolling Kp stats.
- Switched from raw class argmax to probability-based category mapping.
- Tightened and retuned the 5-class label boundaries multiple times.

Main result:

- These changes usually improved some minority-class recall, but often made the model overpredict storms or made `high`/`severe` worse.
- The hardest part is separating `moderate` vs `high` cleanly without hurting `quiet`.

# What worked

- `class_weight="balanced",`
- increasing `quiet` samples
- `class_weight="balanced",` --> `class_weight="balanced_subsample`