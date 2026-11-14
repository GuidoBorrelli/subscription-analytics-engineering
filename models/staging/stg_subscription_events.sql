-- Event revisions are business versions, independent of arrival order.
select event_id, revision, subscription_id, customer_id, effective_date, status, plan_id
from {{ source('raw', 'subscription_events') }}
qualify row_number() over (partition by event_id order by revision desc) = 1
