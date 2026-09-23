# Naming Conventions — VIT-IND-01

Agree on these before either of you commits much code. Changing conventions
halfway through is more painful than picking slightly-imperfect ones now.

## Files & folders

- **Python files/scripts**: `snake_case.py` — e.g. `load_nsl_kdd.py`, `train_gnn.py`
- **Notebooks**: numbered prefix + snake_case, so they sort in the order they're meant to be run:
  - `01_data_exploration.ipynb`
  - `02_feature_engineering.ipynb`
  - `03_anomaly_detection_baseline.ipynb`
  - `04_gnn_training.ipynb`
  - `05_rl_agent_training.ipynb`
  - Put them all in a top-level `notebooks/` folder, not scattered inside module folders.
- **SQL files**: `snake_case.sql`, named by what they do — `schema.sql`, `seed_data.sql`
- **React components**: `PascalCase.jsx` — e.g. `AlertsTable.jsx`, `GraphView.jsx`
- **Config/env files**: `.env.example` committed (with placeholder values), `.env` gitignored

## Folders (matches the repo structure from the build guide)

```
backend/
  ingestion/
  features/
  models/          # anomaly_detector/, gnn/, rl_agent/  — one subfolder per model
  graph/
  api/
notebooks/
frontend/
docs/
```

## Database naming

- Tables: `snake_case`, singular — `network_event`, not `NetworkEvents` or `network_events`
- Columns: `snake_case` — `src_bytes`, not `srcBytes`
- Foreign keys: `<referenced_table>_id` — `event_id`, `alert_id`
- Booleans: `is_` / `has_` prefix — `is_attack`, `has_response`

## Git

- **Branches**: `<track>/<feature>` — `person-a/gnn-training`, `person-b/alerts-dashboard`
  (or use your names if you prefer: `atharva/data-ingestion`)
- **Commits**: short imperative present tense — `"Add NSL-KDD batch loader"`, not
  `"added stuff"` or `"fixed it"`. If a commit does two unrelated things, split it.
- **PR titles**: `[Track] What it does` — `[Detection] Add anomaly detection baseline`

## Notebooks specifically — the part that actually causes problems

Jupyter notebooks store cell *outputs* (including big data tables, plots, error
tracebacks) as part of the `.ipynb` file itself. Committed as-is, this means:
- Every re-run creates a noisy diff even if the code didn't change
- Merge conflicts in notebooks are painful — they conflict on JSON metadata, not just code
- Accidentally committed error outputs/stack traces look bad in review

Two ways to handle it, pick one before you push your first notebook:

1. **Simplest**: strip outputs before every commit.
   ```
   pip install nbstripout
   nbstripout --install    # run once per clone, auto-strips on every commit
   ```
2. **If you want outputs visible in GitHub's preview** (e.g. for showing model
   training curves without making the reviewer re-run everything): keep outputs,
   but restart-and-run-all before committing so the notebook is in a clean,
   reproducible state — no orphaned cell-execution-order weirdness (`In [17]`
   followed by `In [4]`).

Either way: **never commit a notebook with a stack trace or half-finished
experiment as the last cell output** — clean it up first.

## Model artifacts

- Trained model files (`.pt`, `.pkl`, `.h5`) → **do not commit to git**, they're
  large and non-diffable. Add to `.gitignore`:
  ```
  *.pt
  *.pkl
  *.h5
  backend/ingestion/data/
  ```
- Instead, commit the training script/notebook that produces them, and note the
  final metrics (accuracy, F1, etc.) in a `MODEL_CARD.md` or in the notebook
  itself, so anyone can retrain and get the same result.
