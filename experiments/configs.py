"""
Per-dataset configuration for the unified analysis pipeline.

Single source of truth for:
  - Where each dataset's CSV lives
  - Which web-interface domain it was deployed against
  - The (alpha, lambda) hyperparameters that were ACTUALLY DEPLOYED at runtime

Adding a new dataset (e.g., wines once it launches) means adding one entry here.
The pipeline (pipeline.py) reads this file to drive every command.

The 'deployed' hyperparameters are what the JS used at runtime, NOT necessarily
the optimal values. The pipeline produces two analysis variants per dataset:
  - 'deployed': pre-registered analysis using the deployed (alpha, lambda).
  - 'optimal':  exploratory analysis using the calibration-derived optimum.
The optimum is found by calibrate_methods.py and stored under
experiments/outputs/<dataset>/calibration/optima.json.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENTS_DIR = REPO_ROOT / "experiments"
OUTPUTS_DIR     = EXPERIMENTS_DIR / "outputs"


# ============================================================================
# Datasets
# ============================================================================
# Keys are short identifiers used as CLI args and as subdirectory names under
# experiments/outputs/.
#
# Fields:
#   data        Path to the Qualtrics CSV (relative to REPO_ROOT).
#   domain      The web-interface/outputs/<domain>/ folder name. Must match
#               what the JS used at runtime.
#   deployed    {"alpha": float, "lambda": float} — what the JS actually used.
#   label       Display label for figures and tables.
#   n_dims      Number of LLM-discovered dimensions K.
#   include_in_paper
#               If True, this dataset is included in the joint paper figures.
#               Set False for pilots that aren't part of the main paper claims.
DATASETS = {
    "dilemmas": {
        "data":     EXPERIMENTS_DIR / "dilemmas" / "data.csv",
        "domain":   "dailydilemmas",
        "deployed": {"alpha": 2.0, "lambda": 0.01},
        "label":    "Moral dilemmas",
        "n_dims":   10,
        "include_in_paper": True,
    },
    "movies": {
        "data":     EXPERIMENTS_DIR / "movies" / "data.csv",
        "domain":   "movies_100",
        "deployed": {"alpha": 1.0, "lambda": 0.005},
        "label":    "Movies",
        "n_dims":   10,
        "include_in_paper": True,
    },
    "movies_pilot": {
        "data":     EXPERIMENTS_DIR / "movies_pilot" / "data.csv",
        "domain":   "movies_100",
        "deployed": {"alpha": 1.0, "lambda": 0.005},
        "label":    "Movies (pilot)",
        "n_dims":   10,
        "include_in_paper": False,
    },
}


def paper_datasets():
    """Return list of dataset keys flagged for paper inclusion."""
    return [k for k, v in DATASETS.items() if v.get("include_in_paper")]


def output_dir(dataset, sub=None):
    """Canonical output directory for a dataset (optionally a subfolder)."""
    base = OUTPUTS_DIR / dataset
    return base / sub if sub else base


def paper_output_dir():
    return OUTPUTS_DIR / "paper"


def decomposition_output_dir():
    return OUTPUTS_DIR / "decomposition"
