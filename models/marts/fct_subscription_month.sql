{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['subscription_id', 'month_start'],
    on_schema_change='fail'
) }}

with changed_subscriptions as (
    select subscription_id, source_sequence
    from {{ ref('int_subscription_watermarks') }}
    {% if is_incremental() %}
    where source_sequence > (select coalesce(max(source_sequence), 0) from {{ this }})
    {% endif %}
), subscriptions as (
    select subscription_id, min(customer_id) as customer_id
    from {{ ref('stg_subscription_events') }}
    group by subscription_id
), month_end_states as (
    select
        changes.subscription_id,
        subscriptions.customer_id,
        months.month_start,
        events.event_id as source_event_id,
        events.revision as source_revision,
        events.plan_id,
        coalesce(events.status, 'not_started') as status,
        changes.source_sequence
    from changed_subscriptions as changes
    join subscriptions using (subscription_id)
    cross join {{ ref('dim_month') }} as months
    left join {{ ref('stg_subscription_events') }} as events
        on changes.subscription_id = events.subscription_id
        and events.effective_date <= months.month_end
    qualify row_number() over (
        partition by changes.subscription_id, months.month_start
        order by events.effective_date desc, events.event_id desc
    ) = 1
)
select
    states.*,
    case when states.status = 'active' then plans.monthly_price_cents else 0 end as mrr_cents
from month_end_states as states
left join {{ ref('dim_plan') }} as plans using (plan_id)
