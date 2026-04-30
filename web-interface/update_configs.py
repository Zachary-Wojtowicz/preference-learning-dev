#!/usr/bin/env python3
"""Update all experiment_config.json files with inference conditions and domain-specific categories.

Usage:
    cd web-interface
    python3 update_configs.py
"""
import json
import glob

# Domain-specific categories: "You {phrase} {dimension}"
MOVIES_CATEGORIES = [
    {"key": "skip",       "phrase": "prefer to skip",   "label": "Prefer to skip",  "mult": -1.5},
    {"key": "not_into",   "phrase": "aren\u2019t into", "label": "Aren\u2019t into", "mult": -1.0},
    {"key": "indifferent","phrase": "are indifferent to","label": "Indifferent",      "mult":  0.0},
    {"key": "like",       "phrase": "like",             "label": "Like",             "mult":  1.0},
    {"key": "love",       "phrase": "love",             "label": "Love",             "mult":  1.5},
]

SCRUPLES_CATEGORIES = [
    {"key": "discount",    "phrase": "discount",          "label": "Discount",          "mult": -1.5},
    {"key": "look_past",   "phrase": "look past",         "label": "Look past",         "mult": -1.0},
    {"key": "neutral",     "phrase": "are neutral about", "label": "Neutral",           "mult":  0.0},
    {"key": "value",       "phrase": "value",             "label": "Value",             "mult":  1.0},
    {"key": "deeply_care", "phrase": "deeply care about", "label": "Deeply care about", "mult":  1.5},
]

WINES_CATEGORIES = [
    {"key": "avoid",      "phrase": "prefer to avoid",  "label": "Prefer to avoid",  "mult": -1.5},
    {"key": "not_into",   "phrase": "aren\u2019t into", "label": "Aren\u2019t into", "mult": -1.0},
    {"key": "indifferent","phrase": "are indifferent to","label": "Indifferent",      "mult":  0.0},
    {"key": "like",       "phrase": "like",             "label": "Like",             "mult":  1.0},
    {"key": "love",       "phrase": "love",             "label": "Love",             "mult":  1.5},
]

DOMAIN_CATEGORIES = {
    "movies":          MOVIES_CATEGORIES,
    "movies_100":      MOVIES_CATEGORIES,
    "movies_50":       MOVIES_CATEGORIES,
    "moral dilemmas":  SCRUPLES_CATEGORIES,
    "scruples":        SCRUPLES_CATEGORIES,
    "scruples_dilemmas": SCRUPLES_CATEGORIES,
    "everyday moral dilemmas": SCRUPLES_CATEGORIES,
    "dailydilemmas":   SCRUPLES_CATEGORIES,
    "wines":           WINES_CATEGORIES,
    "wines_100":       WINES_CATEGORIES,
}

DEFAULT_COMPARISON = {
    "lambda_standard":     10.0,
    "lambda_partial":      1.0,
    "slider_prior_weight": 1.0,
    "n_dimensions_shown":  10,
    "eval_format":         "top_bottom_bars",  # or "inference_list"
    "n_per_side":          5,
    "most_valued_label":   "Most valued",
    "least_valued_label":  "Least valued",
    # choice_only excluded: that condition collects no feedback signal, so the
    # comparison/evaluation step has nothing meaningful to show.
    "show_for_conditions": [
        "choice_readonly_sliders", "choice_adjustable_sliders",
        "choice_checkboxes", "inference_affirm", "inference_categories",
    ],
}

DEFAULT_INSTRUCTIONS = {
    "training": (
        "<h1>Practice</h1>"
        "<p>Before the main task, you’ll do a few short <strong>practice trials</strong> to learn the preference dimensions used in this study.</p>"
        "<p>Each practice trial shows one dimension and asks which option is more aligned with it. After you click, we’ll tell you whether you were right.</p>"
    ),
    "feedback": (
        "<h1>Main Task</h1>"
        "<p>You will be shown pairs of options. For each pair, <strong>click the one you prefer</strong>.</p>"
    ),
}

INFERENCE_CONDITIONS = {
    "inference_affirm": {
        "label": "Inferences: Affirm / Remove",
        "description": "Affirm or remove model inferences about your preferences.",
        "show_sliders": False,
        "sliders_adjustable": False,
        "show_checkboxes": False,
        "show_inferences": "affirm",
    },
    "inference_categories": {
        "label": "Inferences: Category Selection",
        "description": "Adjust the category for each inference about your preferences.",
        "show_sliders": False,
        "sliders_adjustable": False,
        "show_checkboxes": False,
        "show_inferences": "categories",
    },
}

paths = glob.glob("outputs/*/experiment_config.json") + ["experiment_config.json"]

for path in paths:
    try:
        with open(path) as f:
            cfg = json.load(f)
    except Exception as e:
        print(f"  SKIP {path}: {e}")
        continue

    # Remove old inference condition
    c = cfg.get("conditions", {})
    c.pop("choice_inferences", None)

    # Add both new inference conditions
    c.update(INFERENCE_CONDITIONS)
    cfg["conditions"] = c
    cfg["default_condition"] = "inference_categories"

    # Add domain-specific categories
    domain = cfg.get("domain", "")
    cats = DOMAIN_CATEGORIES.get(domain, MOVIES_CATEGORIES)
    cfg["inference_categories"] = cats

    # Defaults for trial counts (preserve existing if already set)
    cfg.setdefault("num_trials_per_participant", 20)
    cfg.setdefault("num_training_trials", 5)

    # Inference category assignment method:
    #   "perdim" — quintile boundaries computed per-dimension (default)
    #   "pooled" — one global set of boundaries shared across all dimensions
    cfg.setdefault("categorization", "perdim")

    # Default instructions (preserve any existing per-domain edits)
    ins = cfg.get("instructions") or {}
    for k, v in DEFAULT_INSTRUCTIONS.items():
        ins.setdefault(k, v)
    cfg["instructions"] = ins

    # Default comparison block (preserve any existing per-domain edits)
    comp = cfg.get("comparison") or {}
    for k, v in DEFAULT_COMPARISON.items():
        comp.setdefault(k, v)
    cfg["comparison"] = comp

    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"  Updated {path} (domain={domain}, {len(cats)} categories)")

print("\nDone. All configs updated.")
