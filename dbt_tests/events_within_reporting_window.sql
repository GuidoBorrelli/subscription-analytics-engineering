-- This bounded demonstration starts with no opening subscriptions.
-- Reject out-of-window data rather than silently misclassifying opening balances.
select *
from {{ ref('stg_subscription_events') }}
where effective_date < '{{ var("reporting_start") }}'::date
   or effective_date > last_day('{{ var("reporting_end") }}'::date)
