with source as (

    select * from {{ ref('raw_assessments') }}

)

select
    learner_id,
    case when pre_score between 0 and 100 then pre_score end as pre_score,
    case when post_score between 0 and 100 then post_score end as post_score,
    -- flag scores we nulled because they were impossible (null post_score from dropout stays unflagged)
    (pre_score is not null and pre_score not between 0 and 100)
        or (post_score is not null and post_score not between 0 and 100) as has_invalid_score,
    case when lower(trim(project_completed)) = 'yes' then 1 else 0 end as project_completed
from source
