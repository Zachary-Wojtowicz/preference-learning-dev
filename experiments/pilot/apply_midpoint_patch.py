#!/usr/bin/env python3
"""
Apply the midpoint replacement patch to simulation, calibration, and web interface.

Usage:
    cd ~/Dropbox/academics/research/working/nlp/coding/preference-learning-dev
    python experiments/pilot/apply_midpoint_patch.py

What it does:
  For visible dimensions, replaces U_tk with the midpoint of the selected
  category's quintile bin (rather than multiplying U_tk by a feedback scalar).

  Ũ_tk = midpoint[selected_cat, k]    if dim k was visible
  Ũ_tk = U_tk                          if dim k was NOT visible

Changes three files:
  1. simulation/run_simulation.py
  2. experiments/pilot/calibrate_from_pilot.py
  3. web-interface/index.html
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # preference-learning-dev/


def patch_simulation():
    """Patch simulation/run_simulation.py"""
    path = ROOT / "simulation" / "run_simulation.py"
    code = path.read_text()

    # 1. Add perdim_bin_midpoints if not present
    if "def perdim_bin_midpoints" not in code:
        anchor = "    return boundaries\n"
        insert = '''    return boundaries


def perdim_bin_midpoints(values_pool, n_cats=5):
    """For each dimension k, compute the midpoint of each of the n_cats
    quintile bins. Returns (n_cats, K) array.

    Uses the symmetric distribution {v, -v} to match
    perdim_quintile_boundaries. Midpoints are at quantiles
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
        # Find the LAST occurrence of "return boundaries\n" (in perdim_quintile_boundaries)
        idx = code.rfind(anchor)
        if idx < 0:
            print("  WARNING: could not find 'return boundaries' anchor")
        else:
            code = code[:idx] + insert + code[idx + len(anchor):]
            print("  Added perdim_bin_midpoints()")
    else:
        print("  perdim_bin_midpoints already exists, skipping")

    # 2. Compute bin_midpoints in run_simulation(), add to ctx
    if "bin_midpoints" not in code:
        code = code.replace(
            "    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))",
            "    quintile_bounds = perdim_quintile_boundaries(pool_proj, n_cats=len(DEFAULT_MULTS))\n"
            "    bin_midpoints = perdim_bin_midpoints(pool_proj, n_cats=len(DEFAULT_MULTS))"
        )
        code = code.replace(
            '"quintile_bounds": quintile_bounds, "mults": mults,',
            '"quintile_bounds": quintile_bounds, "bin_midpoints": bin_midpoints, "mults": mults,'
        )
        print("  Added bin_midpoints computation and ctx entry")

    # 3. Add bin_midpoints to simulate_one_user destructuring
    if 'bin_midpoints = ctx["bin_midpoints"]' not in code:
        code = code.replace(
            '    quintile_bounds = ctx["quintile_bounds"]',
            '    quintile_bounds = ctx["quintile_bounds"]\n'
            '    bin_midpoints = ctx["bin_midpoints"]'
        )
        print("  Added bin_midpoints destructuring in simulate_one_user")

    # 4. Change lam_traj storage from multiplier to midpoint
    old_lam = "                applied = apply_noise(applied, mults, args.participant_noise, rng)\n                lam_traj[t, k] = applied"
    new_lam = ("                applied = apply_noise(applied, mults, args.participant_noise, rng)\n"
               "                cat_idx = int(np.argmin(np.abs(mults - applied)))\n"
               "                lam_traj[t, k] = bin_midpoints[cat_idx, k]  # store midpoint")
    if old_lam in code:
        code = code.replace(old_lam, new_lam)
        print("  Changed lam_traj to store midpoints")
    else:
        print("  WARNING: could not find lam_traj assignment pattern")

    # 5. Change U_adj construction from alpha-blend to direct replacement
    # Find the block that builds U_adj_full
    old_uadj = '''        alpha = getattr(args, "feedback_alpha", 1.0)
        feedback_full = np.ones_like(U_full)
        if cond != "choice_only":
            feedback_full[visible_traj] = ((1.0 - alpha)
                                            + alpha * lam_traj[visible_traj])
        U_adj_full = feedback_full * U_full'''
    new_uadj = '''        # Midpoint replacement: for visible dims, replace U with the
        # midpoint of the participant's selected category bin.
        # For invisible dims, keep raw U (passthrough).
        U_adj_full = U_full.copy()
        if cond != "choice_only":
            U_adj_full[visible_traj] = lam_traj[visible_traj]'''
    if old_uadj in code:
        code = code.replace(old_uadj, new_uadj)
        print("  Changed U_adj to midpoint replacement")
    else:
        print("  WARNING: could not find U_adj alpha-blend block")

    path.write_text(code)
    print(f"  ✓ Wrote {path}")


def patch_calibration():
    """Patch experiments/pilot/calibrate_from_pilot.py"""
    path = ROOT / "experiments" / "pilot" / "calibrate_from_pilot.py"
    code = path.read_text()

    # 1. Add perdim_bin_midpoints if not present
    if "def perdim_bin_midpoints" not in code:
        # Insert after sigmoid function
        anchor = "    return 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))\n"
        idx = code.find(anchor)
        if idx >= 0:
            insert = '''

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
            code = code[:idx + len(anchor)] + insert + code[idx + len(anchor):]
            print("  Added perdim_bin_midpoints()")

    # 2. Add bin_midpoints computation in main(), and update build_per_trial_arrays call
    if "bin_midpoints" not in code:
        # Add computation after G = V @ V.T
        code = code.replace(
            '    print(f"  K={K}, N options={len(option_ids)}")',
            '    print(f"  K={K}, N options={len(option_ids)}")\n\n'
            '    # Compute per-dim bin midpoints for midpoint replacement\n'
            '    mu = npz.get("mean_embedding", np.zeros(V.shape[1])).astype(np.float64)\n'
            '    centered = embeddings - mu[np.newaxis, :]\n'
            '    pool_proj = centered @ V.T\n'
            '    bin_midpoints = perdim_bin_midpoints(pool_proj, n_cats=5)\n'
            '    CAT_KEYS = ["skip", "not_into", "indifferent", "like", "love"]'
        )
        print("  Added bin_midpoints computation in main()")

    # 3. Change build_per_trial_arrays to accept and use bin_midpoints
    old_sig = "def build_per_trial_arrays(participant, embeddings, V, oid_to_idx, K):"
    new_sig = "def build_per_trial_arrays(participant, embeddings, V, oid_to_idx, K,\n                           bin_midpoints=None, cat_keys=None):"
    if old_sig in code:
        code = code.replace(old_sig, new_sig)
        print("  Updated build_per_trial_arrays signature")

    # Change multiplier storage to midpoint
    old_mult_line = '            raw_lam[t, k] = float(info.get("multiplier", 0.0))'
    new_mult_block = '''            cat_key = info.get("category", "indifferent")
            if bin_midpoints is not None and cat_keys is not None and cat_key in cat_keys:
                cat_idx = cat_keys.index(cat_key)
                raw_lam[t, k] = bin_midpoints[cat_idx, k]
            else:
                raw_lam[t, k] = float(info.get("multiplier", 0.0))'''
    if old_mult_line in code:
        code = code.replace(old_mult_line, new_mult_block)
        print("  Changed raw_lam to store midpoints")

    # 4. Update call site to pass bin_midpoints
    old_call = ("            deltas, U, raw_lam, vis, y = build_per_trial_arrays(\n"
                "                p, embeddings, V, oid_to_idx, K)")
    new_call = ("            deltas, U, raw_lam, vis, y = build_per_trial_arrays(\n"
                "                p, embeddings, V, oid_to_idx, K,\n"
                "                bin_midpoints=bin_midpoints, cat_keys=CAT_KEYS)")
    if old_call in code:
        code = code.replace(old_call, new_call)
        print("  Updated build_per_trial_arrays call site")

    # 5. Change U_adj construction to direct replacement
    old_uadj_cal = """    scaled_lam = np.where(visible_mask, scale * raw_lam, 1.0)
    feedback = (1.0 - alpha) + alpha * scaled_lam
    feedback = np.where(visible_mask, feedback, 1.0)
    U_adj = U * feedback"""
    new_uadj_cal = """    # Midpoint replacement: visible dims get the stored bin midpoint;
    # invisible dims keep raw U.  scale/alpha params are now unused.
    U_adj = U.copy()
    U_adj[visible_mask] = raw_lam[visible_mask]"""
    if old_uadj_cal in code:
        code = code.replace(old_uadj_cal, new_uadj_cal)
        print("  Changed U_adj to midpoint replacement")
    else:
        print("  WARNING: could not find U_adj alpha-blend block in calibration")

    path.write_text(code)
    print(f"  ✓ Wrote {path}")


def patch_web_interface():
    """Patch web-interface/index.html"""
    path = ROOT / "web-interface" / "index.html"
    code = path.read_text()

    # 1. Add dimMidpoints global
    if "dimMidpoints" not in code:
        code = code.replace(
            "var dimQuantiles=null;",
            "var dimQuantiles=null;\nvar dimMidpoints=null;"
        )
        print("  Added dimMidpoints global")

    # 2. Add computeDimMidpoints function after computeDimQuantiles
    if "computeDimMidpoints" not in code:
        midpoints_fn = '''
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
'''
        # Insert after the closing of computeDimQuantiles
        anchor = "  dimQuantiles=computeDimQuantiles();"
        if anchor in code:
            code = code.replace(anchor, midpoints_fn + "  dimQuantiles=computeDimQuantiles();\n  dimMidpoints=computeDimMidpoints();")
            print("  Added computeDimMidpoints() and initialization")
    else:
        print("  Added computeDimMidpoints() function")

    # 3. Change U_adj construction in buildEvalInputs to use midpoints
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
      // Midpoint replacement: map category → bin midpoint for this dimension
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
    if old_uadj_js in code:
        code = code.replace(old_uadj_js, new_uadj_js)
        print("  Changed U_adj to midpoint replacement in buildEvalInputs")
    else:
        print("  WARNING: could not find U_adj JS block")

    path.write_text(code)
    print(f"  ✓ Wrote {path}")


if __name__ == "__main__":
    print("Applying midpoint replacement patch...\n")

    print("[1/3] Simulation:")
    try:
        patch_simulation()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[2/3] Calibration:")
    try:
        patch_calibration()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\n[3/3] Web interface:")
    try:
        patch_web_interface()
    except Exception as e:
        print(f"  ERROR: {e}")

    print("\nDone. Re-run calibration to test:")
    print("  python experiments/pilot/calibrate_from_pilot.py \\")
    print("    --pilot-csv experiments/pilot/data.csv \\")
    print("    --embeddings-parquet datasets/dailydilemmas/selected_actions-embedded.parquet \\")
    print("    --directions method_directions/outputs/dailydilemmas/directions.npz \\")
    print("    --option-id-column action_id \\")
    print("    --output-dir experiments/pilot/calibration_midpoint")
