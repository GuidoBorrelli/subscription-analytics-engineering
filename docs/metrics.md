# Metric contract

Scope: fictional monthly CHF subscriptions, month-end states, no opening subscriptions before the reporting window. The demonstration maintainer owns the definitions. These are declared assumptions, not adopted definitions from a real business.

| Metric | Definition | Interpretation |
| --- | --- | --- |
| Closing MRR | Sum of active monthly plan prices at month end | Contracted recurring run rate, not revenue recognition |
| Opening MRR | Previous reporting month's closing MRR | Zero in the first configured month |
| New MRR | Positive MRR after zero, with no previous active month in the window | First month-end activation |
| Reactivation MRR | Positive MRR after zero, with an earlier active month | Returning month-end subscription |
| Expansion MRR | Positive increase between two active month ends | Net increase; not every within-month upgrade |
| Contraction MRR | Positive decrease between two active month ends | Stored as a positive amount subtracted from the bridge |
| Churn MRR | Previous positive MRR when closing MRR is zero | Stored as a positive amount subtracted from the bridge |
| Active subscriptions | Count of subscriptions with positive closing MRR | One per subscription |
| Active customers | Distinct customer IDs with an active subscription | A customer can own multiple subscriptions |
| Churned subscriptions | Positive previous balance and zero closing balance | Does not imply the customer has no other subscriptions |

All SQL amounts are integer CHF cents. Presentation divides by 100. There is no FX conversion, rounding allocation, proration, trial status, discount, tax or invoice model. Subscription IDs and customer IDs are deliberately distinct entities.

Events use calendar dates, not timestamps. The most recent effective event on or before the month end determines the state. Activating and cancelling within one month can leave both month-end balances at zero and contributes no MRR movement. For activation funnels or intra-month churn, a separate event-grain metric would be required.

**Historical impact:** a higher event revision or a late event can change earlier month-end states and every dependent movement. The incremental model rebuilds the entire affected subscription history. The report reflects the latest accepted business revisions, not what was known at a historical arrival time.

Tests reconcile the bridge exactly and compare manually computed cases to outputs. Test expectations include two subscriptions for one customer, expansion, cancellation, reactivation, late contraction and out-of-order revisions.
