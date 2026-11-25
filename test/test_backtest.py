import numpy as np
import pytest

import config
from backtest import simulate

T = 20


@pytest.fixture(autouse=True)
def short_test_period(monkeypatch):
    monkeypatch.setattr(config, "TEST_DAYS", T)


def run(y, start, rop_value, level, moq=1, weeks_up_to=1):
    n = y.shape[0]
    F = np.zeros((T, n))
    L = np.full((T, n), float(level))
    price_day = np.full((n, y.shape[1]), 10.0)
    fn = lambda f, lv: np.full_like(f, float(rop_value))
    return simulate(y, np.array(start), price_day, F, L, fn, 1, weeks_up_to, moq)


def test_with_plenty_of_stock_every_sale_is_met():
    y = np.ones((1, 40))
    m = run(y, [1], rop_value=1000, level=7)
    assert m["demand"][0] == 20
    assert m["sold"][0] == m["demand"][0]
    assert m["lost_margin"][0] == 0


def test_with_no_stock_every_sale_is_lost():
    y = np.ones((1, 40))
    m = run(y, [1], rop_value=0, level=0)
    assert m["sold"][0] == 0
    # 20 units x $10 x (1 - cost share) of lost margin
    assert m["lost_margin"][0] == pytest.approx(20 * 10 * (1 - config.COGS_SHARE))


def test_days_before_the_item_is_on_sale_are_ignored():
    y = np.ones((1, 40))
    m = run(y, [11], rop_value=1000, level=7)    # on sale from day 11
    assert m["demand"][0] == 10                  # only days 11 to 20 count
    assert m["sold"][0] == 10


def test_minimum_order_size_raises_stock_held():
    y = np.zeros((1, 40))
    y[0, 0] = 1                                  # one sale on the first day
    small = run(y, [1], rop_value=2, level=1, moq=1)
    big = run(y, [1], rop_value=2, level=1, moq=6)
    assert small["orders"][0] == 1
    assert big["orders"][0] == 1
    assert big["inv_units"][0] > small["inv_units"][0]