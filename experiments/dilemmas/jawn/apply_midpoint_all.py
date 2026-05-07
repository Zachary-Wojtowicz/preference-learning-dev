#!/usr/bin/env python3
"""
Apply midpoint replacement to ALL three files.
Reads each file, applies targeted replacements, writes back.

Usage:
    cd ~/Dropbox/academics/research/working/nlp/coding/preference-learning-dev
    python apply_midpoint_all.py
"""
import sys, re
from pathlib import Path

ROOT = Path.cwd()
ERRORS = []

def report(msg):
    print(f"  {msg}")

def warn(msg):
    print(f"  ⚠ {msg}")
    ERRORS.append(msg)

def safe_replace(code, old, new, label):
    if old in code:
        code = code.replace(old, new)
        report(f"✓ {label}")
    else:
        warn(f"Pattern not found for: {label}")
    return code


# =========================================================================
# 1. SIMULATION (simulation/run_simulation.py)
# =========================================================================
print("\n[1/3] Patching simulation/run_simulation.py ...")
sim_path = ROOT / "simulation" / "run_simulation.py"
sim = sim_path.read_text()

# 1a. Add perdim_bin_midpoints function (if not present)
if "def perdim_bin_midpoints" not in sim:
    # Find the end of perdim_quintile_boundaries (its last "return boundaries")
    # We need to insert after the function, before the next function
    anchor = "def value_to_mult("
    insert_fn = '''
def perdim_bin_midpoints(values_pool, n_cats=5):
    """For each dimension k, compute the midpoint of each quintile bin.
    Returns (n_cats, K) array. Midpoints are at quantiles
    [1/(2n), 3/(2n), ..., (2n-1)/(2n)] — center of mass of each bin.
    """
    T, K = values_pool.shape
    midpoint_qs = np.array([(2 * i + 1) / (2 * n_cats) for i in range(n_cats)])
    midpoints = np.zeros((n_cats, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        midpoints[:, k] = np.quantile(symm, midpoint_qs)
    return midpoints


'''
    sim = sim.replace(anchor, insert_fn + anchor)
    report("✓ Added perdim_bin_midpoints()")
else:
    report("perdim_bin_midpoints already exists")

# 1b. Compute bin_midpoints in run_simulation()
if "bin_midpoints = perdim_bin_midpoints" not in sim:
    sim = safe_replace(sim,
        "    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))",
        "    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))\n"
        "    bin_midpoints = perdim_bin_midpoints(pool_proj, n_cats=len(DEFAULT_MULTS))",
        "Added bin_midpoints computation")

# 1c. Add bin_midpoints to ctx
if '"bin_midpoints"' not in sim:
    sim = safe_replace(sim,
        '"quintile_bounds": quintile_bounds, "mults": mults,',
        '"quintile_bounds": quintile_bounds, "bin_midpoints": bin_midpoints, "mults": mults,',
        "Added bin_midpoints to ctx")

# 1d. Destructure bin_midpoints in simulate_one_user
if 'bin_midpoints = ctx["bin_midpoints"]' not in sim:
    sim = safe_replace(sim,
        '    quintile_bounds = ctx["quintile_bounds"]',
        '    quintile_bounds = ctx["quintile_bounds"]\n    bin_midpoints = ctx["bin_midpoints"]',
        "Added bin_midpoints destructuring")

# 1e. Change lam_traj to store midpoints instead of multipliers
old_lam = """                applied = apply_noise(applied, mults, args.participant_noise, rng)
                lam_traj[t, k] = applied"""
new_lam = """                applied = apply_noise(applied, mults, args.participant_noise, rng)
                cat_idx = int(np.argmin(np.abs(mults - applied)))
                lam_traj[t, k] = bin_midpoints[cat_idx, k]"""
sim = safe_replace(sim, old_lam, new_lam, "Changed lam_traj to store midpoints")

# 1f. Change U_adj construction to direct replacement
old_uadj = """        alpha = getattr(args, "feedback_alpha", 1.0)
        feedback_full = np.ones_like(U_full)
        if cond != "choice_only":
            feedback_full[visible_traj] = ((1.0 - alpha)
                                            + alpha * lam_traj[visible_traj])
        U_adj_full = feedback_full * U_full"""
new_uadj = """        # Midpoint replacement: for visible dims, replace U with the
        # midpoint of the participant's selected category bin.
        # For invisible dims, keep raw U (passthrough).
        U_adj_full = U_full.copy()
        if cond != "choice_only":
            U_adj_full[visible_traj] = lam_traj[visible_traj]"""
sim = safe_replace(sim, old_uadj, new_uadj, "Changed U_adj to midpoint replacement")

sim_path.write_text(sim)
report(f"Wrote {sim_path}")


# =========================================================================
# 2. CALIBRATION (experiments/pilot/calibrate_from_pilot.py)
# =========================================================================
print("\n[2/3] Patching experiments/pilot/calibrate_from_pilot.py ...")
cal_path = ROOT / "experiments" / "pilot" / "calibrate_from_pilot.py"
cal = cal_path.read_text()

# 2a. Add perdim_bin_midpoints function
if "def perdim_bin_midpoints" not in cal:
    # Insert after sigmoid function
    anchor_pat = re.compile(r'(def sigmoid\(x\):.*?return 1\.0 / \(1\.0 \+ np\.exp\(-np\.clip\(x, -50, 50\)\)\)\n)', re.DOTALL)
    m = anchor_pat.search(cal)
    if m:
        insert_fn = '''

def perdim_bin_midpoints(values_pool, n_cats=5):
    """Bin midpoints for each dimension. Returns (n_cats, K)."""
    T, K = values_pool.shape
    midpoint_qs = np.array([(2 * i + 1) / (2 * n_cats) for i in range(n_cats)])
    midpoints = np.zeros((n_cats, K))
    for k in range(K):
        v = values_pool[:, k]
        symm = np.concatenate([v, -v])
        midpoints[:, k] = np.quantile(symm, midpoint_qs)
    return midpoints

'''
        cal = cal[:m.end()] + insert_fn + cal[m.end():]
        report("✓ Added perdim_bin_midpoints()")
    else:
        warn("Could not find sigmoid function as anchor")
else:
    report("perdim_bin_midpoints already exists")

# 2b. Add bin_midpoints computation in main()
if "bin_midpoints = perdim_bin_midpoints" not in cal:
    cal = safe_replace(cal,
        '    print(f"  K={K}, N options={len(option_ids)}")',
        '''    print(f"  K={K}, N options={len(option_ids)}")

    # Compute per-dim bin midpoints for midpoint replacement
    _npz2 = np.load(args.directions)
    _mu = _npz2["mean_embedding"].astype(np.float64) if "mean_embedding" in _npz2 else np.zeros(V.shape[1])
    _centered = embeddings - _mu[np.newaxis, :]
    _pool_proj = _centered @ V.T
    bin_midpoints = perdim_bin_midpoints(_pool_proj, n_cats=5)
    CAT_KEYS = ["skip", "not_into", "indifferent", "like", "love"]''',
        "Added bin_midpoints computation in main()")

# 2c. Update build_per_trial_arrays signature
old_sig = "def build_per_trial_arrays(participant, embeddings, V, oid_to_idx, K):"
new_sig = "def build_per_trial_arrays(participant, embeddings, V, oid_to_idx, K,\n                           bin_midpoints=None, cat_keys=None):"
cal = safe_replace(cal, old_sig, new_sig, "Updated build_per_trial_arrays signature")

# 2d. Change raw_lam storage to use midpoints
old_rawlam = '            raw_lam[t, k] = float(info.get("multiplier", 0.0))'
new_rawlam = '''            cat_key = info.get("category", "indifferent")
            if bin_midpoints is not None and cat_keys is not None and cat_key in cat_keys:
                cat_idx = cat_keys.index(cat_key)
                raw_lam[t, k] = bin_midpoints[cat_idx, k]
            else:
                raw_lam[t, k] = float(info.get("multiplier", 0.0))'''
cal = safe_replace(cal, old_rawlam, new_rawlam, "Changed raw_lam to store midpoints")

# 2e. Update call site to pass bin_midpoints
old_call = """            deltas, U, raw_lam, vis, y = build_per_trial_arrays(
                p, embeddings, V, oid_to_idx, K)"""
new_call = """            deltas, U, raw_lam, vis, y = build_per_trial_arrays(
                p, embeddings, V, oid_to_idx, K,
                bin_midpoints=bin_midpoints, cat_keys=CAT_KEYS)"""
cal = safe_replace(cal, old_call, new_call, "Updated build_per_trial_arrays call site")

# 2f. Change U_adj construction to direct replacement
old_uadj_cal = """    scaled_lam = np.where(visible_mask, scale * raw_lam, 1.0)
    feedback = (1.0 - alpha) + alpha * scaled_lam
    feedback = np.where(visible_mask, feedback, 1.0)
    U_adj = U * feedback"""
new_uadj_cal = """    # Midpoint replacement: visible dims get the stored bin midpoint;
    # invisible dims keep raw U. scale/alpha params are now unused.
    U_adj = U.copy()
    U_adj[visible_mask] = raw_lam[visible_mask]"""
cal = safe_replace(cal, old_uadj_cal, new_uadj_cal, "Changed U_adj to midpoint replacement")

cal_path.write_text(cal)
report(f"Wrote {cal_path}")


# =========================================================================
# 3. WEB INTERFACE (web-interface/index.html)
# =========================================================================
print("\n[3/3] Patching web-interface/index.html ...")
web_path = ROOT / "web-interface" / "index.html"
web = web_path.read_text()

# 3a. Add dimMidpoints global
if "dimMidpoints" not in web:
    web = safe_replace(web,
        "var dimQuantiles=null;",
        "var dimQuantiles=null;\nvar dimMidpoints=null;",
        "Added dimMidpoints global")

# 3b. Add computeDimMidpoints function and initialization
if "computeDimMidpoints" not in web:
    midpoints_fn = """
function computeDimMidpoints(){
  if(!trials||trials.length===0)return null;
  var nCats=CATEGORIES.length;if(nCats<2)return null;
  var byDim={};
  trials.forEach(function(t){if(!t.sliders)return;
    t.sliders.forEach(function(s){
      var did=s.dimension_id;if(did==null)return;
      if(!byDim[did])byDim[did]=[];
      var va=Number(s.value_if_a),vb=Number(s.value_if_b);
      if(Number.isFinite(va))byDim[did].push(va);
      if(Number.isFinite(vb))byDim[did].push(vb);
    });
  });
  var out={};
  Object.keys(byDim).forEach(function(did){
    var arr=byDim[did].slice().sort(function(a,b){return a-b;});
    if(arr.length<nCats){out[did]=null;return;}
    var mids=[];
    for(var i=0;i<nCats;i++){
      var q=(2*i+1)/(2*nCats);
      var idx=Math.min(Math.floor(q*(arr.length-1)),arr.length-1);
      mids.push(arr[idx]);
    }
    out[did]=mids;
  });
  return out;
}
"""
    web = safe_replace(web,
        "  dimQuantiles=computeDimQuantiles();",
        midpoints_fn + "  dimQuantiles=computeDimQuantiles();\n  dimMidpoints=computeDimMidpoints();",
        "Added computeDimMidpoints() and initialization")

# 3c. Change U_adj construction in buildEvalInputs to use midpoints
old_uadj_js = """  responses.forEach(function(r,t){
    if(!r.inference_values)return;
    Object.keys(r.inference_values).forEach(function(did){
      var idx=dimIds.indexOf(did);if(idx<0)return;
      var m=r.inference_values[did].multiplier;
      if(typeof m!=='number'||!isFinite(m))return;
      U_adj[t][idx]=m*U[t][idx]; // scale the design matrix entry
      sums[idx]+=m;counts[idx]+=1;
    });
  });"""
new_uadj_js = """  responses.forEach(function(r,t){
    if(!r.inference_values)return;
    Object.keys(r.inference_values).forEach(function(did){
      var idx=dimIds.indexOf(did);if(idx<0)return;
      var info=r.inference_values[did];
      // Midpoint replacement: map category -> bin midpoint for this dimension
      var cat=info.category;
      var catIdx=-1;
      for(var ci=0;ci<CATEGORIES.length;ci++){if(CATEGORIES[ci].key===cat){catIdx=ci;break;}}
      var dimId=dims[idx].dimension_id;
      if(catIdx>=0&&dimMidpoints&&dimMidpoints[dimId]&&dimMidpoints[dimId][catIdx]!=null){
        U_adj[t][idx]=dimMidpoints[dimId][catIdx];
      }
      var m=info.multiplier;
      if(typeof m==='number'&&isFinite(m)){sums[idx]+=m;counts[idx]+=1;}
    });
  });"""
web = safe_replace(web, old_uadj_js, new_uadj_js, "Changed U_adj to midpoint replacement in buildEvalInputs")

web_path.write_text(web)
report(f"Wrote {web_path}")


# =========================================================================
# Summary
# =========================================================================
print("\n" + "=" * 60)
if ERRORS:
    print(f"⚠ {len(ERRORS)} warnings:")
    for e in ERRORS:
        print(f"  - {e}")
else:
    print("✓ All patches applied successfully!")
print("=" * 60)
print("\nRe-run calibration:")
print("  python experiments/pilot/calibrate_from_pilot.py \\")
print("    --pilot-csv experiments/pilot/data.csv \\")
print("    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \\")
print("    --directions method_directions/outputs/dailydilemmas/directions.npz \\")
print("    --option-id-column action_id \\")
print("    --output-dir experiments/pilot/calibration_midpoint")
