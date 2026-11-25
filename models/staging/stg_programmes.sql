with source as (

    select * from {{ ref('raw_programmes') }}

)

select
    programme_id,
    programme_name,
    n_sessions,
    duration_weeks,
    cast(start_date as date) as start_date,
    cast(end_date as date) as end_date
from source
