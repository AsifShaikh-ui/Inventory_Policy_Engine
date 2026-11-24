import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import config  # noqa: E402

PROCESSED = config.PROCESSED_DIR
RULE_NAMES = {
    "current": "Order up to reorder point + 1 week",
    "batch4": "Order up to reorder point + 4 weeks",
    "batch8": "Order up to reorder point + 8 weeks",
    "batch4_moq6": "4 weeks, minimum 6 units per order",
}
POLICY_NAMES = {
    "ours_low": "Ours, low service",
    "ours_default": "Ours, default service",
    "ours_high": "Ours, high service",
}

st.set_page_config(page_title="Inventory Policy Engine", layout="wide")


@st.cache_data
def load_policy():
    return pd.read_parquet(PROCESSED / "policy_params.parquet")


@st.cache_data
def load_recent():
    return pd.read_parquet(PROCESSED / "app_recent_sales.parquet")


@st.cache_data
def load_tradeoff():
    return pd.read_parquet(PROCESSED / "app_tradeoff.parquet")


def label(s: str) -> str:
    if s in POLICY_NAMES:
        return POLICY_NAMES[s]
    return f"Baseline {s.replace('base_', '').replace('d', '')} days"


st.title("Inventory Policy Engine")
st.caption(
    "M5 Walmart sales data. All costs and the 7-day delivery time are assumptions, "
    "and backtest results are hypothetical outcomes under those assumptions, not measured savings."
)

policy = load_policy()
tab1, tab2 = st.tabs(["Item reorder point", "Policy trade-off"])

# ---------------- Tab 1 ----------------
with tab1:
    c1, c2 = st.columns(2)
    store = c1.selectbox("Store", sorted(policy["store_id"].unique()))
    items = sorted(policy.loc[policy["store_id"] == store, "item_id"])
    item = c2.selectbox("Item", items)

    row = policy[(policy["store_id"] == store) & (policy["item_id"] == item)].iloc[0]
    rop = int(np.ceil(row["reorder_point"]))
    target = config.SERVICE_LEVELS[row["abc"]]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Class", f"{row['abc']} / {row['demand_class']}")
    m2.metric("Forecast, next 7 days", f"{row['forecast_7d']:.1f} units")
    m3.metric("Safety stock", f"{row['safety_stock']:.1f} units")
    m4.metric("Reorder point", f"{rop} units")

    st.info(
        f"When stock on hand plus stock already on order falls to **{rop} units or fewer**, "
        f"place an order. Delivery is assumed to take {config.LEAD_TIME_DAYS} days. "
        f"The buffer is sized so that about {target:.0%} of 7-day periods are covered "
        f"for a class {row['abc']} item."
    )
    if row["source"] == "pooled":
        st.caption(
            "Too few similar items to size this buffer on its own, so it uses the "
            "value for the whole ABC class."
        )

    recent = load_recent()
    hist = recent[(recent["store_id"] == store) & (recent["item_id"] == item)]
    fig = px.bar(hist, x="date", y="units_sold", title="Daily units sold, last 120 days")
    fig.update_layout(yaxis_title="Units", xaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

# ---------------- Tab 2 ----------------
with tab2:
    tr = load_tradeoff()
    c1, c2, c3 = st.columns(3)
    rule = c1.selectbox(
        "Order rule", list(RULE_NAMES), format_func=lambda r: RULE_NAMES[r]
    )
    order_cost = c2.slider("Cost per order ($)", 0.0, 10.0, float(config.ORDER_COST), 0.5)
    classes = c3.multiselect("ABC classes", ["A", "B", "C"], default=["A", "B", "C"])

    t = tr[(tr["rule"] == rule) & (tr["abc"].isin(classes))]
    if t.empty:
        st.warning("Pick at least one class.")
    else:
        g = t.groupby("scenario")[
            ["demand", "sold", "inv_value", "orders", "lost_margin"]
        ].sum()
        out = pd.DataFrame(index=g.index)
        out["Fill rate"] = g["sold"] / g["demand"]
        out["Stock value ($)"] = g["inv_value"] / config.TEST_DAYS
        out["Holding ($)"] = g["inv_value"] * config.HOLDING_RATE / 365
        out["Ordering ($)"] = g["orders"] * order_cost
        out["Lost margin ($)"] = g["lost_margin"]
        out["Total cost ($)"] = (
            out["Holding ($)"] + out["Ordering ($)"] + out["Lost margin ($)"]
        )
        out["Policy"] = [label(s) for s in out.index]
        out["Type"] = np.where(out.index.str.startswith("ours"), "Our policy", "Baseline")

        best_base = out[out["Type"] == "Baseline"]["Total cost ($)"].min()
        best_ours = out[out["Type"] == "Our policy"]["Total cost ($)"].min()
        k1, k2, k3 = st.columns(3)
        k1.metric("Best baseline total cost", f"${best_base:,.0f}")
        k2.metric("Best of our policies", f"${best_ours:,.0f}")
        k3.metric("Ours is lower by", f"{1 - best_ours / best_base:.1%}")

        fig = px.scatter(
            out, x="Stock value ($)", y="Fill rate", color="Type", text="Policy",
            title="Service vs stock held: further up and left is better",
        )
        fig.update_traces(textposition="top center", marker_size=11)
        st.plotly_chart(fig, use_container_width=True)

        show = out.set_index("Policy").drop(columns="Type")
        st.dataframe(
            show.style.format({
                "Fill rate": "{:.3f}", "Stock value ($)": "{:,.0f}",
                "Holding ($)": "{:,.0f}", "Ordering ($)": "{:,.0f}",
                "Lost margin ($)": "{:,.0f}", "Total cost ($)": "{:,.0f}",
            }),
            use_container_width=True,
        )
        st.caption(
            "Backtest on the last 224 days, 7-day delivery, lost sales not backordered. "
            "Compare policies within one order rule, not across rules."
        )