# Assumptions: Inventory Policy Engine

Every result in this project depends on the assumptions below. The M5 data has sales and prices only: no stock levels, costs, or lead times. So any cost or savings figure is a **hypothetical outcome under these assumptions**, never measured savings.

Status key:
- **Confirmed**: checked against the data
- **Unverified**: believed true, not yet checked
- **Proposed**: starting value I chose; to be reviewed and tested with sensitivity analysis

---

## A. Data assumptions

| # | Assumption | Status | How it gets checked |
|---|---|---|---|
| A1 | A zero in `sales_train_evaluation` means no units were sold that day | Confirmed (by data definition) | n/a |
| A2 | An item-store series is "available" from its first price week; zeros before that are structural, not demand zeros | Confirmed | Checked on all 30,490 series: none sold before its first price week (0.00%); every series has at least one sale. Result in `availability.parquet` |
| A3 | Observed sales are used as a proxy for demand. Stockouts may hide true demand (censored demand), and the data cannot show them | Confirmed as a limitation | Stated in the case study |
| A4 | Calendar days d_1942 to d_1969 have no sales and are excluded | Confirmed | Row counts in validation |
| A5 | The price of an item in a store is constant within a week | Unverified | Follows from the prices file having one row per item, store, and week |
| A6 | `d_n` maps to a real date through the calendar's `d` column | Confirmed | Join check in ingest |

## B. Business assumptions (not in the data)

All values here are **Proposed** and will be varied in a sensitivity analysis, not treated as facts.

| # | Assumption | Proposed value | Why this value |
|---|---|---|---|
| B1 | Supplier lead time | 7 days, same for all items | Simple starting point; real lead times vary by supplier |
| B2 | Target service level (share of demand met from stock) | 95% | Common retail starting target |
| B3 | Annual holding cost, as a share of item value | 20% | Common textbook range; covers capital, storage, shrinkage |
| B4 | Cost of goods, as a share of selling price | 70% (so 30% gross margin) | The data has no unit cost, so this stands in for it |
| B5 | Cost of placing one order | $2 per order (chosen by me); tested at $0, $2, $10 | Needed to compare policies that order at different frequencies |
| B6 | Cost of a lost sale | Lost gross margin on the units not sold | Simplest defensible choice; ignores customers lost for good |
| B7 | Baseline policy for comparison | Reorder when stock falls to N days of average sales, for every item; N tested at 7, 14, 21, 30, 45 | A common simple rule that our policy must beat |
| B8 | Order rule used in the backtest | Daily review; when stock plus stock on order is at or below the reorder point (rounded up to whole units), order up to reorder point plus one normal week of demand; delivery after 7 days; unmet demand is lost; each item starts full on its first day on the shelf | Simple rule applied identically to every policy. Known weakness: slow items reorder after almost every sale |

## C. How these assumptions are used

- The backtest replays history under the baseline policy and under our policy, with the same assumptions applied to both.
- Each B assumption gets a sensitivity test (for example lead time of 3, 7, and 14 days) to show which results depend on it.
- Results are reported as "under these assumptions", never as measured savings.

## D. Open items

- Price gaps after launch: checked in `classify.py`. 0 available item-store-days lack a price row, so no gaps after the first price week.
- Decide B5 (ordering cost) and review B1 to B4 before the backtest is written.
- Rounding rule decided: reorder points are rounded up to whole units in the backtest.
- The order rule (B8) creates about 27 orders per series in 224 days. Tested larger batches (4 and 8 weeks, minimum order 6 units) in decision D15; the conclusion held. Weekly review was not tested because it would change the protection period the buffers were fitted for.