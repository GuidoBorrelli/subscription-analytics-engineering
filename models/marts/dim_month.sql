select
    month_start::date as month_start,
    last_day(month_start)::date as month_end
from generate_series(
    '{{ var("reporting_start") }}'::date,
    '{{ var("reporting_end") }}'::date,
    interval '1 month'
) as months(month_start)
