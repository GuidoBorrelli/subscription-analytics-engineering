-- Detect missing months as well as duplicate fact rows.
select subscription_id
from {{ ref('fct_subscription_month') }}
group by subscription_id
having count(*) != (select count(*) from {{ ref('dim_month') }})
    or count(distinct month_start) != count(*)
