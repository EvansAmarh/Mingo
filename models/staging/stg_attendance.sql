with attendance as (

    select * from {{ ref('raw_attendance') }}

),

programmes as (

    select * from {{ ref('stg_programmes') }}

),

enrolments as (

    select distinct learner_id, programme_id from {{ ref('raw_enrolments') }}

)

select
    attendance.learner_id,
    attendance.session_number,
    cast(attendance.session_date as date) as session_date,
    case when lower(trim(attendance.attended)) = 'yes' then 1 else 0 end as attended,
    -- flag, don't delete: out-of-window dates are kept so the mart can exclude them visibly
    cast(attendance.session_date as date)
        between programmes.start_date and programmes.end_date as is_valid_date
from attendance
left join enrolments on attendance.learner_id = enrolments.learner_id
left join programmes on enrolments.programme_id = programmes.programme_id
