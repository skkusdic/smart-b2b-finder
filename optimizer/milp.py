"""
3단계 MILP 최적화
"""
import pandas as pd

try:
    import pulp
    _PULP_AVAILABLE = True
except ImportError:
    _PULP_AVAILABLE = False


def run_stage3(df, am_slots=10, top_n=10, sector_limit=4):
    if len(df) == 0:
        return df
    capacity = min(am_slots, top_n, len(df))
    df = df.copy().reset_index(drop=True)
    max_rev = df["revenue"].max() or 1
    df["_rev_w"] = df["revenue"].fillna(0) / max_rev * 0.3 + 0.7
    df["_obj"]   = df["total_score"] * df["_rev_w"]
    df["_sector"] = df["industry"].fillna("00").astype(str).str[:2]
    if not _PULP_AVAILABLE:
        result = df.nlargest(capacity, "_obj").drop(columns=["_rev_w", "_obj", "_sector"])
        result = result.reset_index(drop=True)
        result.insert(0, "milp_rank", range(1, len(result) + 1))
        return result
    n    = len(df)
    prob = pulp.LpProblem("B2B_Portfolio_Selection", pulp.LpMaximize)
    x    = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    prob += pulp.lpSum(x[i] * float(df.iloc[i]["_obj"]) for i in range(n))
    prob += pulp.lpSum(x) <= capacity
    for sector in df["_sector"].unique():
        idxs = df.index[df["_sector"] == sector].tolist()
        if len(idxs) > sector_limit:
            prob += pulp.lpSum(x[i] for i in idxs) <= sector_limit
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    selected = [i for i in range(n) if pulp.value(x[i]) is not None and pulp.value(x[i]) > 0.5]
    if not selected:
        selected = df["_obj"].nlargest(capacity).index.tolist()
    result = df.iloc[selected].drop(columns=["_rev_w", "_obj", "_sector"]).copy()
    result = result.sort_values("total_score", ascending=False).reset_index(drop=True)
    result.insert(0, "milp_rank", range(1, len(result) + 1))
    return result
