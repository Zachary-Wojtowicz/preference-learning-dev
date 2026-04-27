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
    {"key": "reject",     "phrase": "reject",           "label": "Reject",           "mult": -1.5},
    {"key": "disapprove", "phrase": "disapprove of",    "label": "Disapprove of",    "mult": -1.0},
    {"key": "indifferent","phrase": "are indifferent to","label": "Indifferent",      "mult":  0.0},
    {"key": "understand", "phrase": "understand",       "label": "Understand",       "mult":  1.0},
    {"key": "endorse",    "phrase": "endorse",          "label": "Endorse",          "mult":  1.5},
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
    "scruples_200":    SCRUPLES_CATEGORIES,
    "scruples_dilemmas": SCRUPLES_CATEGORIES,
    "wines":           WINES_CATEGORIES,
    "wines_100":       WINES_CATEGORIES,
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

    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"  Updated {path} (domain={domain}, {len(cats)} categories)")

print("\nDone. All configs updated.")
