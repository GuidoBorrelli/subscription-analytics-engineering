select * from {{ ref('plans') }} where monthly_price_cents <= 0 or currency != 'CHF'
