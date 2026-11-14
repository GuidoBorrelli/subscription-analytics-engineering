select *
from {{ ref('fct_subscription_month') }}
where mrr_cents < 0
   or (status = 'active' and (mrr_cents <= 0 or plan_id is null))
   or (status != 'active' and (mrr_cents != 0 or plan_id is not null))
