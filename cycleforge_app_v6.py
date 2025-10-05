# CycleForge v8 — 4-panel perfect vs actual + composition-aware optimizer
import streamlit as st
import pandas as pd
import math

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
st.sidebar.selectbox("Energy regeneration (info only)", ["1e / 3min"], index=0)

assign_btn = st.sidebar.button("Assign Roles", type="primary")
dl_placeholder = st.sidebar.empty()

st.subheader("Roster Input")
st.caption("Enter player names and attack levels. Level 0 means the attack is unusable; both 0 ⇒ Idle.")
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

def feasible_role(row, role_name, energy_cap):
    r = ROLES[role_name]
    if r["energy"] > energy_cap: return False
    if r["sb"]>0 and int(row["sb_level"])<=0: return False
    if r["mag"]>0 and int(row["mag_level"])<=0: return False
    return True

def calc_feasible_cycles(df, energy_cap, recipe):
    tmp = df.copy()
    for col in ["sb_level","mag_level"]:
        tmp[col] = pd.to_numeric(tmp[col], errors="coerce").fillna(0).astype(int)
    sb_capacity = sum((energy_cap // 7) for _,row in tmp.iterrows() if int(row["sb_level"])>0)
    mag_capacity = sum((energy_cap // 2) for _,row in tmp.iterrows() if int(row["mag_level"])>0)
    c_max = min(recipe["SB_required"], sb_capacity, max(0, (mag_capacity - 6)//3))
    return {"sb_capacity": sb_capacity, "mag_capacity": mag_capacity, "SB_required": c_max, "Mag_required": 6 + 3*c_max}

def pin_desired_roles(df, quotas, energy_cap):
    assigned = {}
    totals = {"sb":0,"mag":0,"energy":0,"sb_points":0,"mag_points":0}
    issues = []
    df = df.copy()
    df["sb_level"] = pd.to_numeric(df["sb_level"], errors="coerce").fillna(0).astype(int)
    df["mag_level"] = pd.to_numeric(df["mag_level"], errors="coerce").fillna(0).astype(int)
    if "desired_role" not in df.columns:
        df["desired_role"] = "Auto"
    remaining_sb = int(quotas["SB_required"])
    remaining_mag = int(quotas["Mag_required"])
    for idx, row in df.iterrows():
        desired = (row.get("desired_role","Auto") or "Auto").strip()
        if desired == "Auto": continue
        if desired not in ROLES: issues.append(f"{row.get('name','(unnamed)')}: unknown role '{desired}' → ignored"); continue
        if not feasible_role(row, desired, energy_cap): issues.append(f"{row.get('name','(unnamed)')}: infeasible desired '{desired}' → Idle"); assigned[idx] = "Idle"; continue
        r = ROLES[desired]
        if r["sb"] > remaining_sb or r["mag"] > remaining_mag: issues.append(f"{row.get('name','(unnamed)')}: desired '{desired}' exceeds remaining quotas → Idle"); assigned[idx] = "Idle"; continue
        assigned[idx] = desired
        remaining_sb -= r["sb"]; remaining_mag -= r["mag"]
        totals["sb"] += r["sb"]; totals["mag"] += r["mag"]; totals["energy"] += r["energy"]
        totals["sb_points"] += pts_sb(row["sb_level"]) * r["sb"]
        totals["mag_points"] += pts_mag(row["mag_level"]) * r["mag"]
    return assigned, totals, remaining_sb, remaining_mag, issues

def assign_by_composition(df, remaining_sb, remaining_mag, energy_cap, pre_assigned):
    df = df.copy()
    df["sb_level"] = pd.to_numeric(df["sb_level"], errors="coerce").fillna(0).astype(int)
    df["mag_level"] = pd.to_numeric(df["mag_level"], errors="coerce").fillna(0).astype(int)
    df["pts_per_sb"] = df["sb_level"].apply(lambda x: pts_sb(int(x)) if int(x)>0 else 0)
    df["pts_per_mag"] = df["mag_level"].apply(lambda x: pts_mag(int(x)) if int(x)>0 else 0)

    assigned = dict(pre_assigned)
    used = set(i for i,r in assigned.items() if r!="Idle")

    both = [i for i,row in df.iterrows() if row["sb_level"]>0 and row["mag_level"]>0 and i not in used]
    sb_only = [i for i,row in df.iterrows() if row["sb_level"]>0 and row["mag_level"]==0 and i not in used]
    mag_only = [i for i,row in df.iterrows() if row["mag_level"]>0 and row["sb_level"]==0 and i not in used]

    def try_comp(c, y, z, x, w):
        if y+z > len(both): return None
        pick1 = sorted(both, key=lambda i: df.loc[i,"pts_per_sb"]*1 + df.loc[i,"pts_per_mag"]*7, reverse=True)[:y]
        rem_both = [i for i in both if i not in pick1]
        pick2 = sorted(rem_both, key=lambda i: df.loc[i,"pts_per_sb"]*2 + df.loc[i,"pts_per_mag"]*3, reverse=True)[:z]
        rem_both2 = [i for i in rem_both if i not in pick2]
        pool_sb = sb_only + rem_both2
        if x > len(pool_sb): return None
        pickx = sorted(pool_sb, key=lambda i: df.loc[i,"pts_per_sb"]*3, reverse=True)[:x]
        rem_both3 = [i for i in rem_both2 if i not in pickx]
        pool_mag = mag_only + rem_both3
        if w > len(pool_mag): return None
        pickw = sorted(pool_mag, key=lambda i: df.loc[i,"pts_per_mag"]*10, reverse=True)[:w]
        la = {}
        for i in pick1: la[i] = "1 SB + 7 Mag"
        for i in pick2: la[i] = "2 SB + 3 Mag"
        for i in pickx: la[i] = "SB-only"
        for i in pickw: la[i] = "Mag-only"
        if len(pick1)!=y or len(pick2)!=z or len(pickx)!=x or len(pickw)!=w: return None
        tot_sb = y*1 + z*2 + x*3
        tot_mag = y*7 + z*3 + w*10
        if tot_sb != c or tot_mag != 6 + 3*c: return None
        tot_energy = y*21 + z*20 + x*21 + w*20
        tot_sb_pts = sum(df.loc[i,"pts_per_sb"]*3 for i in pickx) + sum(df.loc[i,"pts_per_sb"]*2 for i in pick2) + sum(df.loc[i,"pts_per_sb"]*1 for i in pick1)
        tot_mag_pts = sum(df.loc[i,"pts_per_mag"]*10 for i in pickw) + sum(df.loc[i,"pts_per_mag"]*3 for i in pick2) + sum(df.loc[i,"pts_per_mag"]*7 for i in pick1)
        return la, {"sb":tot_sb,"mag":tot_mag,"energy":tot_energy,"sb_points":tot_sb_pts,"mag_points":tot_mag_pts}

    best = None
    for c in range(int(remaining_sb), -1, -1):
        for y in range(0, c+1):
            for z in range(0, c//2 + 1):
                sb_left = c - (y + 2*z)
                if sb_left < 0 or sb_left % 3 != 0: continue
                x = sb_left // 3
                mag_needed = 6 + 3*c
                rest_mag = mag_needed - (7*y + 3*z)
                if rest_mag < 0 or rest_mag % 10 != 0: continue
                w = rest_mag // 10
                if y+z+x+w > len(df): continue
                res = try_comp(c, y, z, x, w)
                if res is None: continue
                la, lt = res
                points = lt["sb_points"] + lt["mag_points"]
                if best is None or c > best[0] or (c == best[0] and points > best[2]):
                    best = (c, la, points, lt)
        if best is not None:
            break
    if best is None:
        return assigned, {"sb":0,"mag":0,"energy":0,"sb_points":0,"mag_points":0}
    for i, rname in best[1].items():
        assigned[i] = rname
    return assigned, best[3]

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
        totals["sb"] += r["sb"]; totals["mag"] += r["mag"]; totals["energy"] += r["energy"]
        totals["sb_points"] += sb_pts; totals["mag_points"] += mag_pts
    out_df = pd.DataFrame(rows)
    role_counts = out_df["role"].value_counts().to_dict()
    return out_df, role_counts, totals

def perfect_mix_example(cycles):
    C = int(cycles)
    target_mag = 6 + 3*C
    best = None
    for y in range(0, C+1):
        for z in range(0, C//2 + 1):
            sb_left = C - (y + 2*z)
            if sb_left < 0 or sb_left % 3 != 0: continue
            x = sb_left // 3
            rest_mag = target_mag - (7*y + 3*z)
            if rest_mag < 0 or rest_mag % 10 != 0: continue
            w = rest_mag // 10
            players = x + y + z + w
            if best is None or players < best[0]:
                best = (players, x, y, z, w)
    if best is None:
        return None
    _, x, y, z, w = best
    return {"Mag-only": w, "SB-only": x, "2 SB / 3 Mag": z, "1 SB + 7 Mag": y}

# ---------- Top row ----------
st.subheader("Cycle Recipe & Feasibility")
recipe = BRACKET_RECIPE[bracket_choice]
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Bracket recipe (_perfect_ round):**")
    st.write(f"- SB casts required: **{recipe['SB_required']}**")
    st.write(f"- Mag casts required: **{recipe['Mag_required']}**")
    st.write(f"- Expected kills: **{recipe['kills']}**")
    st.write(f"- Energy used (team): **{recipe['team_energy_used']}**")
with col2:
    st.markdown("**Perfect Roster**")
    min_sb_cap = math.ceil(recipe["SB_required"]/3)
    min_mag_cap = math.ceil(recipe["Mag_required"]/10)
    st.write(f"- SB-capable players: **minimum {min_sb_cap}** (sb_level > 0)")
    st.write(f"- Mag-capable players: **minimum {min_mag_cap}** (mag_level > 0)")
    mix = perfect_mix_example(recipe["SB_required"])
    st.markdown("**Roles Count (one valid mix):**")
    if mix:
        st.write(f"- Mag-only crew: **{mix.get('Mag-only',0)}**")
        st.write(f"- SB-only crew: **{mix.get('SB-only',0)}**")
        st.write(f"- 2 SB / 3 Mag crew: **{mix.get('2 SB / 3 Mag',0)}**")
        st.write(f"- 1 SB / 7 Mag crew: **{mix.get('1 SB + 7 Mag',0)}**")
    else:
        st.info("No exact perfect mix exists (should not happen for standard brackets).")

st.markdown("---")

# ---------- Run planner ----------
plan_df = None
role_counts = {"Mag-only":0,"SB-only":0,"2 SB / 3 Mag":0,"1 SB + 7 Mag":0}
totals = None
pin_issues = []

if assign_btn:
    try:
        quotas = calc_feasible_cycles(players_df, energy_cap, recipe)
        pre_assigned, pin_totals, rem_sb, rem_mag, pin_issues = pin_desired_roles(players_df.copy(), quotas, energy_cap)
        assigned, comp_totals = assign_by_composition(players_df.copy(), rem_sb, rem_mag, energy_cap, pre_assigned)
        plan_df, role_counts, totals = build_output(players_df.copy(), assigned)
    except Exception as e:
        st.error(f"Assignment failed: {e}")

# ---------- Bottom row ----------
col3, col4 = st.columns(2)
with col3:
    st.markdown("**Feasible Cycle (based on roster)**")
    if totals is None:
        st.write("- SB casts possible: x / x")
        st.write("- Mag casts usable: x / x")
        st.write("- Expected kills: x / x")
        st.write("- Team energy used: x/x")
        st.write("- Expected Mag points (team total): 0")
        st.write("- Expected SB points (team total): 0")
        st.write("- Expected grand total (Mag + SB): 0")
    else:
        assigned_sb = int(totals["sb"])
        assigned_mag = int(totals["mag"])
        kills = (1 if assigned_mag >= 6 else 0) + assigned_sb
        kills = min(kills, recipe["kills"])
        st.write(f"- SB casts possible: **{assigned_sb} / {recipe['SB_required']}**")
        st.write(f"- Mag casts usable: **{assigned_mag} / {recipe['Mag_required']}**")
        st.write(f"- Expected kills: **{kills} / {recipe['kills']}**")
        st.write(f"- Team energy used: **{totals['energy']}** (sum of assigned roles)")
        st.write(f"- Expected Mag points (team total): **{int(totals['mag_points']):,}**")
        st.write(f"- Expected SB points (team total): **{int(totals['sb_points']):,}**")
        st.write(f"- Expected grand total (Mag + SB): **{int(totals['sb_points']+totals['mag_points']):,}**")
        short_sb = max(0, recipe["SB_required"] - assigned_sb)
        short_mag = max(0, recipe["Mag_required"] - assigned_mag)
        if short_sb>0 or short_mag>0:
            st.info(f"Shortfall vs perfect round: SB {short_sb}, Mag {short_mag}.")
        if pin_issues:
            st.warning("Pinned role notices:\n- " + "\n- ".join(pin_issues))

with col4:
    st.markdown("**Roster capability:**")
    cap_df = players_df.copy()
    for col in ["sb_level","mag_level"]:
        if col not in cap_df: cap_df[col] = 0
        cap_df[col] = pd.to_numeric(cap_df[col], errors="coerce").fillna(0).astype(int)
    sb_capable = int((cap_df['sb_level']>0).sum())
    mag_capable = int((cap_df['mag_level']>0).sum())
    st.write(f"- SB-capable players: **{sb_capable}** (sb_level > 0)")
    st.write(f"- Mag-capable players: **{mag_capable}** (mag_level > 0)")
    st.markdown("**Roles Count:**")
    st.write("- Mag-only crew:", role_counts.get("Mag-only",0))
    st.write("- SB-only crew:", role_counts.get("SB-only",0))
    st.write("- 2 SB / 3 Mag crew:", role_counts.get("2 SB / 3 Mag",0))
    st.write("- 1 SB / 7 Mag crew:", role_counts.get("1 SB + 7 Mag",0))

# ---------- Plan Details + Download ----------
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
