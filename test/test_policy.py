import numpy as np
import pandas as pd
import pytest

from policy import build_safety_table, forecasts_at


def make_csum(y):
    y = np.atleast_2d(np.asarray(y, dtype=float))
    return np.concatenate([np.zeros((y.shape[0], 1)), np.cumsum(y, axis=1)], axis=1)


def test_steady_demand_gives_seven_times_daily_rate():
    csum = make_csum(np.ones((1, 100)))          # sells 1 unit every day
    _, forecast, level = forecasts_at(csum, np.array([1]), 60)
    assert forecast[0] == pytest.approx(7.0)
    assert level[0] == pytest.approx(7.0)


def test_days_before_the_item_existed_are_not_averaged_in():
    y = np.zeros((1, 100))
    y[0, 49:] = 2                                # on sale from day 50, sells 2 a day
    _, forecast, level = forecasts_at(make_csum(y), np.array([50]), 60)
    assert forecast[0] == pytest.approx(14.0)    # 2 per day x 7, not diluted by zeros
    assert level[0] == pytest.approx(14.0)


def test_forecast_uses_no_data_after_the_forecast_day():
    y = np.ones((1, 100))
    y2 = y.copy()
    y2[0, 60:] = 999                             # change only the future
    _, f1, l1 = forecasts_at(make_csum(y), np.array([1]), 60)
    _, f2, l2 = forecasts_at(make_csum(y2), np.array([1]), 60)
    assert f1[0] == f2[0]
    assert l1[0] == l2[0]


def test_item_not_yet_on_sale_does_not_crash():
    n_hist, forecast, _ = forecasts_at(make_csum(np.ones((1, 100))), np.array([80]), 60)
    assert n_hist[0] == -19
    assert np.isfinite(forecast[0])


def test_safety_ratio_matches_service_level_percentile():
    ev = pd.DataFrame({
        "abc": "A", "demand_class": "smooth",
        "miss_ratio": np.linspace(0, 1, 1001),
    })
    t = build_safety_table(ev, {"A": 0.98})
    row = t.iloc[0]
    assert row["ss_ratio"] == pytest.approx(0.98)
    assert row["source"] == "group"


def test_higher_service_level_gives_bigger_buffer():
    ev = pd.DataFrame({
        "abc": "A", "demand_class": "smooth",
        "miss_ratio": np.linspace(0, 1, 1001),
    })
    low = build_safety_table(ev, {"A": 0.90}).iloc[0]["ss_ratio"]
    high = build_safety_table(ev, {"A": 0.99}).iloc[0]["ss_ratio"]
    assert high > low


def test_small_group_falls_back_to_pooled_value():
    smooth = pd.DataFrame({
        "abc": "A", "demand_class": "smooth",
        "miss_ratio": np.linspace(0, 1, 1001),
    })
    erratic = pd.DataFrame({
        "abc": "A", "demand_class": "erratic", "miss_ratio": [5.0] * 10,
    })
    ev = pd.concat([smooth, erratic], ignore_index=True)
    t = build_safety_table(ev, {"A": 0.98}).set_index("demand_class")
    assert t.loc["erratic", "source"] == "pooled"
    assert t.loc["erratic", "ss_ratio"] == pytest.approx(
        np.quantile(ev["miss_ratio"], 0.98)
    )


def test_buffer_is_never_negative():
    ev = pd.DataFrame({
        "abc": "A", "demand_class": "smooth", "miss_ratio": [-1.0] * 600,
    })
    t = build_safety_table(ev, {"A": 0.98})
    assert t.iloc[0]["ss_ratio"] == 0.0