select plan_id, plan_name, monthly_price_cents, currency from {{ ref('plans') }}
