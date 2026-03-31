# CLAUDE.md — Preference Elicitation Experiment Prototype

## Overview

Build a simple, self-contained web-based prototype for a psychology experiment on preference elicitation. The entire app is a **single HTML file** (no build step, no framework — plain HTML, CSS, and vanilla JS). It should be clean, minimal, and feel like a professional research tool (think: neutral colors, clear typography, no decorative clutter).

## What the App Does

A participant works through a sequence of **trials**. Each trial presents two text options side by side. The participant clicks one to select it. Upon selection, a panel of **5 labeled sliders** appears below, each pre-populated to a value that depends on which option was chosen. The participant can adjust the sliders, then clicks **Submit** to advance to the next trial. After all trials are complete, the collected response data is displayed on screen as formatted JSON.

## Data Flow

### Input: `trials.json`

The app loads its trial data from a file called `trials.json` in the same directory. The file contains an array of trial objects. Example structure:

```json
[
  {
    "trial_id": "t1",
    "prompt": "Which wine would you prefer to drink tonight?",
    "option_a": {
      "label": "Option A",
      "text": "A bold Napa Cabernet with dark cherry notes, firm tannins, and a long oaky finish."
    },
    "option_b": {
      "label": "Option B",
      "text": "A crisp Sancerre with citrus and flint minerality, light body, and a clean finish."
    },
    "sliders": [
      { "id": "boldness",    "label": "Flavor Boldness",    "value_if_a":  75, "value_if_b": -60 },
      { "id": "sweetness",   "label": "Sweetness",          "value_if_a":  20, "value_if_b": -10 },
      { "id": "complexity",  "label": "Complexity",          "value_if_a":  65, "value_if_b":  30 },
      { "id": "familiarity", "label": "Familiarity",         "value_if_a":  40, "value_if_b":  50 },
      { "id": "food_match",  "label": "Food Pairing Fit",   "value_if_a":  55, "value_if_b":  70 }
    ]
  }
]
```

Key points about the schema:
- `trial_id`: unique string identifier for the trial.
- `prompt`: optional text displayed above the two options (e.g., a question or context).
- `option_a` / `option_b`: each has a short `label` and a longer `text` block.
- `sliders`: exactly 5 slider definitions per trial. Each has:
  - `id`: machine-readable key.
  - `label`: human-readable label shown next to the slider.
  - `value_if_a`: integer in [-100, 100], the pre-populated value if Option A is chosen.
  - `value_if_b`: integer in [-100, 100], the pre-populated value if Option B is chosen.

### Output: displayed JSON

After the final trial is submitted, replace the experiment UI with a results screen that displays the full response data as pretty-printed JSON inside a styled `<pre>` block. The output schema:

```json
{
  "responses": [
    {
      "trial_id": "t1",
      "chosen": "a",
      "slider_values": {
        "boldness": 80,
        "sweetness": 15,
        "complexity": 65,
        "familiarity": 40,
        "food_match": 55
      }
    }
  ]
}
```

- `chosen`: `"a"` or `"b"`.
- `slider_values`: a map from each slider `id` to the participant's final (possibly adjusted) integer value.

## UI / UX Specifications

### Layout & Style
- Centered container, max-width ~800px.
- Neutral background (light gray or white). No heavy colors.
- Clean sans-serif font (system font stack is fine).
- Subtle borders and light shadows for cards — nothing flashy.

### Trial Screen
1. **Progress indicator** at the top: e.g., "Trial 2 of 5".
2. **Prompt text** (if present) displayed above the options.
3. **Two option cards** displayed side by side (or stacked on narrow screens):
   - Each card shows the option label as a heading and the text as body.
   - Cards are clickable. On hover, show a subtle highlight. When one is selected, give it a visible selected state (e.g., colored border) and dim the other slightly.
   - Clicking a different card switches the selection (and re-populates sliders).
4. **Slider panel** — hidden until an option is selected, then revealed with a smooth transition:
   - 5 horizontal range sliders, each on its own row.
   - Each row: label on the left, slider in the middle, current numeric value on the right.
   - Range: -100 to 100, step 1.
   - Sliders are pre-populated to the values from the JSON corresponding to the chosen option.
   - If the participant switches their option selection, slider values reset to the new option's defaults.
5. **Submit button** — appears below the sliders, enabled only after an option is selected. Clicking advances to the next trial (or to the results screen if it's the last trial).

### Results Screen
- Heading: "Experiment Complete"
- Display the output JSON in a `<pre><code>` block with readable formatting.
- Include a "Copy to Clipboard" button.

## Technical Notes

- **No dependencies.** No npm, no CDN imports, no frameworks. Just one `.html` file and one `.json` file.
- Load `trials.json` via `fetch()`. If the fetch fails (e.g., CORS when opening via `file://`), show a friendly error message suggesting the user serve the files via a local server (e.g., `python3 -m http.server`).
- All state lives in JS variables — no localStorage or sessionStorage.
- The app should be functional and testable with the example trial data above. **Ship `trials.json` alongside `index.html` with 3 example trials** so the prototype works out of the box.

## File Deliverables

```
experiment/
├── index.html      # The complete app
└── trials.json     # 3 example trials (realistic-looking dummy data)
```

## What NOT to Do

- Do not use any JS framework or library.
- Do not over-design — this is a research prototype, not a consumer product.
- Do not add features beyond what is described here (no login, no randomization, no server, no database).
- Do not use localStorage or sessionStorage.
