# CycleForge v6 with desired_role overrides
import streamlit as st
import pandas as pd

st.set_page_config(page_title="CycleForge", layout="wide")

MAG_POINTS = {1:300,2:330,3:365,4:400,5:440,6:485,7:535,8:590,9:650,10:715,11:785,12:865,13:950,14:1045,15:1150,16:1265,17:1390,18:1530,19:1685,20:1855}
SB_POINTS  = {1:700,2:850,3:1000,4:1150,5:1300,6:1450,7:1600,8:1750,9:1900,10:2050,11:2200,12:2300,13:2500,14:2650,15:2800,16:2950,17:3100,18:3250,19:3400,20:3550}

def pts_mag(level:int)->int: return MAG_POINTS.get(int(level), 0) if int(level)>0 else 0
def pts_sb(level:int)->int:  return SB_POINTS.get(int(level), 0) if int(level)>0 else 0

ROLES = {
    "SB-only": {"sb":3, "mag":0, "energy":21},
    "1 SB + 7 Mag": {"sb":1, "mag":7, "energy":21},
    "2 SB + 3 Mag": {"sb":2, "mag":3, "energy":20},
    "Mag-only": {"sb":0, "mag":10, "energy":20},
    "Idle": {"sb":0, "mag":0, "energy":0},
    "Auto": {"sb":0, "mag":0, "energy":0},
}

BRACKET_RECIPE = {
    "25": {"SB_required":39, "Mag_required":123, "kills":40, "team_energy_used":"519 / 525"},
    "19": {"SB_required":29, "Mag_required":93,  "kills":30, "team_energy_used":"389 / 399"},
    "13": {"SB_required":20, "Mag_required":66,  "kills":21, "team_energy_used":"272 / 273"},
}

DESIRED_OPTIONS = ["Auto","SB-only","1 SB + 7 Mag","2 SB + 3 Mag","Mag-only","Idle"]

st.sidebar.title("CycleForge")
st.sidebar.caption("Round Cycle Planner")

bracket_choice = st.sidebar.selectbox("Bracket", ["13", "19", "25"], index=0)
energy_cap = st.sidebar.number_input("Energy cap (per player)", min_value=1, max_value=50, value=21, step=1)
regen_info = st.sidebar.selectbox("Energy regeneration (info only)", ["1e / 3min"], index=0)

assign_btn = st.sidebar.button("Assign Roles", type="primary")
dl_placeholder = st.sidebar.empty()

st.subheader("Roster Input")
st.caption("Enter player names and attack levels. Level 0 means the attack is unusable; both 0 => Idle.")
default_players = [{"name": f"Player {i}", "sb_level": 0, "mag_level": 0, "desired_role": "Auto"} for i in range(1, 11)]
players_df = st.data_editor(
    pd.DataFrame(default_players),
    column_config={
        "desired_role": st.column_config.SelectboxColumn("desired_role", options=DESIRED_OPTIONS, help="Optional: force a specific role; leave Auto to let CycleForge decide.")
    },
    num_rows="dynamic",
    use_container_width=True,
    key="players_editor"
)

st.subheader("Cycle Recipe & Feasibility")
recipe = BRACKET_RECIPE[bracket_choice]

colA, colB = st.columns(2)
with colA:
    st.markdown("**Bracket recipe (perfect round):**")
    st.write(f"- SB casts required: **{recipe['SB_required']}**")
    st.write(f"- Mag casts required: **{recipe['Mag_required']}**")
    st.write(f"- Expected kills: **{recipe['kills']}**")
    st.write(f"- Energy used (team): **{recipe['team_energy_used']}**")
    exp_mag_points = st.markdown("- Expected Mag points (team total): —")
    exp_sb_points  = st.markdown("- Expected SB points (team total): —")
    exp_total_points = st.markdown("- Expected grand total (Mag + SB): —")

with colB:
    st.markdown("**Roster capability:**")
    cap_df = players_df.copy()
    for col in ["sb_level","mag_level"]:
        if col not in cap_df: cap_df[col] = 0
        cap_df[col] = pd.to_numeric(cap_df[col], errors="coerce").fillna(0).astype(int)
    sb_capable = int((cap_df['sb_level']>0).sum())
    mag_capable = int((cap_df['mag_level']>0).sum())
    st.write(f"- SB-capable players: **{sb_capable}** (sb_level > 0)")
    st.write(f"- Mag-capable players: **{mag_capable}** (mag_level > 0)")
    role_counts_area = st.container()

st.markdown("---")

def feasible_role(row, role_name, energy_cap):
    r = ROLES[role_name]
    if r["energy"] > energy_cap: return False
    if r["sb"]>0 and int(row["sb_level"])<=0: return False
    if r["mag"]>0 and int(row["mag_level"])<=0: return False
    return True

def calc_feasible_quotas(df, energy_cap, recipe):
    tmp = df.copy()
    for col in ["sb_level","mag_level"]:
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0).astype(int)
    sb_capacity = sum((energy_cap // 7) for _,row in tmp.iterrows() if int(row["sb_level"])>0)
    mag_capacity = sum((energy_cap // 2) for _,row in tmp.iterrows() if int(row["mag_level"])>0)
    max_cycles = min(sb_capacity, max(0, (mag_capacity - 6)//3))
    feasible_sb  = max(0, max_cycles)
    feasible_mag = max(0, 6 + 3*max_cycles)
    SB_required = min(recipe["SB_required"], feasible_sb)
    Mag_required = min(recipe["Mag_required"], feasible_mag)
    return {"sb_capacity": sb_capacity, "mag_capacity": mag_capacity, "max_cycles": max_cycles,
            "SB_required": SB_required, "Mag_required": Mag_required}

def pin_desired_roles(df, quotas, energy_cap):
    assigned = {}
    total_sb = total_mag = total_energy = total_sb_pts = total_mag_pts = 0
    issues = []
    df = df.copy()
    df["sb_level"] = pd.to_numeric(df["sb_level"], errors="coerce").fillna(0).astype(int)
    df["mag_level"] = pd.to_numeric(df["mag_level"], errors="coerce").fillna(0).astype(int)
    if "desired_role" not in df.columns:
        df["desired_role"] = "Auto"
    remaining_sb = int(quotas["SB_required"])
    remaining_mag = int(quotas["Mag_required"])
    for idx, row in df.iterrows():
        desired = (row.get("desired_role", "Auto") or "Auto").strip()
        if desired == "Auto":
            continue
        if desired not in ROLES:
            issues.append(f"{row.get('name','(unnamed)')}: unknown role '{desired}' → ignored")
            continue
        r = ROLES[desired]
        if not feasible_role(row, desired, energy_cap):
            issues.append(f"{row.get('name','(unnamed)')}: infeasible desired '{desired}' → Idle")
            assigned[idx] = "Idle"
            continue
        if r["sb"] > remaining_sb or r["mag"] > remaining_mag:
            issues.append(f"{row.get('name','(unnamed)')}: desired '{desired}' exceeds remaining quotas → Idle")
            assigned[idx] = "Idle"
            continue
        assigned[idx] = desired
        remaining_sb -= r["sb"]
        remaining_mag -= r["mag"]
        total_sb      += r["sb"]
        total_mag     += r["mag"]
        total_energy  += r["energy"]
        total_sb_pts  += pts_sb(int(row["sb_level"])) * r["sb"]
        total_mag_pts += pts_mag(int(row["mag_level"])) * r["mag"]
    totals = {"sb": total_sb, "mag": total_mag, "energy": total_energy, "sb_points": total_sb_pts, "mag_points": total_mag_pts}
    return assigned, totals, remaining_sb, remaining_mag, issues

def assign_roles_sb_first(df, remaining_sb, remaining_mag, energy_cap, pre_assigned):
    df = df.copy()
    df["sb_level"] = pd.to_numeric(df["sb_level"], errors="coerce").fillna(0).astype(int)
    df["mag_level"] = pd.to_numeric(df["mag_level"], errors="coerce").fillna(0).astype(int)
    df["pts_per_sb"] = df["sb_level"].apply(lambda x: pts_sb(int(x)) if int(x)>0 else 0)
    df["pts_per_mag"] = df["mag_level"].apply(lambda x: pts_mag(int(x)) if int(x)>0 else 0)
    assigned = dict(pre_assigned)
    # Phase A: SB
    sb_roles = ["SB-only","2 SB + 3 Mag","1 SB + 7 Mag"]
    candidates = []
    for idx, row in df.iterrows():
        if idx in assigned and assigned[idx] != "Idle":
            continue
        for role_name in sb_roles:
            if not feasible_role(row, role_name, energy_cap): continue
            r = ROLES[role_name]
            if r["sb"] == 0: continue
            total_val = row["pts_per_sb"]*r["sb"] + row["pts_per_mag"]*r["mag"]
            v_per_sb = total_val / r["sb"]
            mag_per_sb = r["mag"] / r["sb"]
            candidates.append((v_per_sb, total_val, -mag_per_sb, idx, role_name, r))
    candidates.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    for _, _, _, idx, role_name, r in candidates:
        if remaining_sb <= 0: break
        if idx in assigned and assigned[idx] != "Idle": continue
        if r["sb"] <= remaining_sb and r["mag"] <= remaining_mag:
            assigned[idx] = role_name
            remaining_sb -= r["sb"]
            remaining_mag -= r["mag"]
    # Phase B: Mag
    mag_candidates = []
    for idx, row in df.iterrows():
        if idx in assigned and assigned[idx] != "Idle": continue
        if not feasible_role(row, "Mag-only", energy_cap): continue
        if remaining_mag < ROLES["Mag-only"]["mag"]: continue
        per_mag = row["pts_per_mag"]
        total_val = per_mag * ROLES["Mag-only"]["mag"]
        mag_candidates.append((per_mag, total_val, idx))
    mag_candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    for per_mag, total_val, idx in mag_candidates:
        if remaining_mag < ROLES["Mag-only"]["mag"]: break
        assigned[idx] = "Mag-only"
        remaining_mag -= ROLES["Mag-only"]["mag"]
    return assigned, remaining_sb, remaining_mag

def build_output(df, assigned):
    df = df.copy()
    df["sb_level"] = pd.to_numeric(df["sb_level"], errors="coerce").fillna(0).astype(int)
    df["mag_level"] = pd.to_numeric(df["mag_level"], errors="coerce").fillna(0).astype(int)
    df["pts_per_sb"] = df["sb_level"].apply(lambda x: pts_sb(int(x)) if int(x)>0 else 0)
    df["pts_per_mag"] = df["mag_level"].apply(lambda x: pts_mag(int(x)) if int(x)>0 else 0)
    rows = []
    totals = {"sb":0,"mag":0,"energy":0,"sb_points":0,"mag_points":0}
    for idx, row in df.iterrows():
        role_name = assigned.get(idx, "Idle")
        r = ROLES[role_name]
        sb_pts = row["pts_per_sb"] * r["sb"]
        mag_pts = row["pts_per_mag"] * r["mag"]
        rows.append({
            "name": row.get("name",""),
            "sb_level": int(row["sb_level"]),
            "mag_level": int(row["mag_level"]),
            "role": role_name,
            "pts_per_sb": int(row["pts_per_sb"]),
            "pts_per_mag": int(row["pts_per_mag"]),
            "sb_casts": r["sb"],
            "mag_casts": r["mag"],
            "sb_points": int(sb_pts),
            "mag_points": int(mag_pts),
            "player_points": int(sb_pts + mag_pts),
            "energy_used": r["energy"],
        })
        totals["sb"] += r["sb"]
        totals["mag"] += r["mag"]
        totals["energy"] += r["energy"]
        totals["sb_points"] += sb_pts
        totals["mag_points"] += mag_pts
    out_df = pd.DataFrame(rows)
    role_counts = out_df["role"].value_counts().to_dict()
    return out_df, role_counts, totals

# ---------- Run ----------
plan_df = None
role_counts = {"Mag-only":0,"SB-only":0,"2 SB + 3 Mag":0,"1 SB + 7 Mag":0}
feasible = None
totals = None
rem_sb = rem_mag = None
pin_issues = []

if assign_btn:
    try:
        quotas = calc_feasible_quotas(players_df, energy_cap, recipe)
        feasible = quotas
        pre_assigned, pin_totals, rem_sb, rem_mag, pin_issues = pin_desired_roles(players_df.copy(), quotas, energy_cap)
        assigned, rem_sb, rem_mag = assign_roles_sb_first(players_df.copy(), rem_sb, rem_mag, energy_cap, pre_assigned)
        plan_df, role_counts, totals = build_output(players_df.copy(), assigned)
        # update expected
        total_mag_points = int(plan_df["mag_points"].sum())
        total_sb_points  = int(plan_df["sb_points"].sum())
        total_points     = int(plan_df["player_points"].sum())
        exp_mag_points.markdown(f"- Expected Mag points (team total): **{total_mag_points:,}**")
        exp_sb_points.markdown(f"- Expected SB points (team total): **{total_sb_points:,}**")
        exp_total_points.markdown(f"- Expected grand total (Mag + SB): **{total_points:,}**")
    except Exception as e:
        st.error(f"Assignment failed: {e}")

with role_counts_area:
    st.markdown("**Roles Count:**")
    st.write("- Mag-only crew:", role_counts.get("Mag-only",0))
    st.write("- SB-only crew:", role_counts.get("SB-only",0))
    st.write("- 2 SB / 3 Mag crew:", role_counts.get("2 SB + 3 Mag",0))
    st.write("- 1 SB / 7 Mag crew:", role_counts.get("1 SB + 7 Mag",0))

if feasible is not None and totals is not None:
    st.markdown("### Feasible Cycle (based on roster)")
    assigned_sb = totals["sb"]
    assigned_mag = totals["mag"]
    kills = 1 + feasible["SB_required"]
    st.write(f"- SB casts possible: **{assigned_sb} / {recipe['SB_required']}**")
    st.write(f"- Mag casts usable: **{assigned_mag} / {recipe['Mag_required']}**")
    st.write(f"- Expected kills: **{kills} / {recipe['kills']}**")
    st.write(f"- Team energy used: **{totals['energy']}** (sum of assigned roles)")
    st.write(f"- Expected Mag points (team total): **{totals['mag_points']:,}**")
    st.write(f"- Expected SB points (team total): **{totals['sb_points']:,}**")
    st.write(f"- Expected grand total (Mag + SB): **{(totals['sb_points']+totals['mag_points']):,}**")
    if pin_issues:
        st.warning("Pinned role notices:\n- " + "\n- ".join(pin_issues))
    if (rem_sb and rem_sb>0) or (rem_mag and rem_mag>0):
        st.info(f"Shortfall vs perfect round: SB {max(0, rem_sb or 0)}, Mag {max(0, rem_mag or 0)}.")

st.subheader("Plan Details")
locked_order = ["name","sb_level","mag_level","role","pts_per_sb","pts_per_mag","sb_casts","mag_casts","sb_points","mag_points","player_points","energy_used"]
if plan_df is not None:
    for col in locked_order:
        if col not in plan_df.columns: plan_df[col] = 0
    plan_df = plan_df[locked_order]
    st.dataframe(plan_df, use_container_width=True, hide_index=True)
    csv = plan_df.to_csv(index=False).encode("utf-8")
    dl_placeholder.download_button("Download Plan CSV", data=csv, file_name="Plan.csv", mime="text/csv")
else:
    st.info("Click 'Assign Roles' to generate the plan.")
