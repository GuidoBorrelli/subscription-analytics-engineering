select customer_id, segment from {{ source('raw', 'customers') }}
