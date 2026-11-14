-- Grain: one month. Changes within a month are netted at the month-end snapshot.
with prior_state as (
    select
        *,
        lag(mrr_cents, 1, 0) over (
            partition by subscription_id order by month_start
        ) as prior_mrr_cents,
        coalesce(max(case when mrr_cents > 0 then 1 else 0 end) over (
            partition by subscription_id order by month_start
            rows between unbounded preceding and 1 preceding
        ), 0) as previously_active
    from {{ ref('fct_subscription_month') }}
), movements as (
    select
        *,
        case when prior_mrr_cents = 0 and mrr_cents > 0 and previously_active = 0
            then mrr_cents else 0 end as new_mrr_cents,
        case when prior_mrr_cents = 0 and mrr_cents > 0 and previously_active = 1
            then mrr_cents else 0 end as reactivation_mrr_cents,
        case when prior_mrr_cents > 0 and mrr_cents > prior_mrr_cents
            then mrr_cents - prior_mrr_cents else 0 end as expansion_mrr_cents,
        case when mrr_cents > 0 and mrr_cents < prior_mrr_cents
            then prior_mrr_cents - mrr_cents else 0 end as contraction_mrr_cents,
        case when prior_mrr_cents > 0 and mrr_cents = 0
            then prior_mrr_cents else 0 end as churn_mrr_cents
    from prior_state
)
select
    months.month_start,
    coalesce(sum(prior_mrr_cents), 0)::bigint as opening_mrr_cents,
    coalesce(sum(new_mrr_cents), 0)::bigint as new_mrr_cents,
    coalesce(sum(reactivation_mrr_cents), 0)::bigint as reactivation_mrr_cents,
    coalesce(sum(expansion_mrr_cents), 0)::bigint as expansion_mrr_cents,
    coalesce(sum(contraction_mrr_cents), 0)::bigint as contraction_mrr_cents,
    coalesce(sum(churn_mrr_cents), 0)::bigint as churn_mrr_cents,
    coalesce(sum(mrr_cents), 0)::bigint as closing_mrr_cents,
    count(*) filter (where mrr_cents > 0) as active_subscriptions,
    count(distinct customer_id) filter (where mrr_cents > 0) as active_customers,
    count(*) filter (where prior_mrr_cents > 0 and mrr_cents = 0) as churned_subscriptions
from {{ ref('dim_month') }} as months
left join movements on months.month_start = movements.month_start
group by months.month_start
