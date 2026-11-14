select *
from {{ ref('mart_mrr_movements') }}
where opening_mrr_cents + new_mrr_cents + reactivation_mrr_cents + expansion_mrr_cents
    - contraction_mrr_cents - churn_mrr_cents != closing_mrr_cents
