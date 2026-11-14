-- Include every received revision, even when an older version arrives late.
select subscription_id, max(ingestion_sequence) as source_sequence
from {{ source('raw', 'subscription_events') }}
group by subscription_id
