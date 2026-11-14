-- Two distinct current events on the same effective date have no defined business order.
select subscription_id, effective_date
from {{ ref('stg_subscription_events') }}
group by subscription_id, effective_date
having count(*) > 1
