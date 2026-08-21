-- Staging model: CMS Complications & Deaths (hospital clinical outcomes)
-- Same staging pattern as stg_hospital_readmissions: rename to ccn, SAFE_CAST
-- numerics (suppression -> NULL), flag suppression, keep footnote.

with source as (

    select * from {{ source('raw', 'hospital_complications') }}

),

renamed as (

    select
        facility_id                          as ccn,
        facility_name                        as hospital_name,
        state,
        citytown                             as city,
        zip_code,

        measure_id,
        measure_name,
        compared_to_national,                -- e.g. 'No Different Than National Rate'

        safe_cast(denominator as int64)      as denominator,
        safe_cast(score as float64)          as score,
        safe_cast(lower_estimate as float64) as lower_estimate,
        safe_cast(higher_estimate as float64) as higher_estimate,

        case
            when score is null
                 or trim(score) in ('Not Available', 'N/A', '')
            then true
            else false
        end                                  as is_suppressed,
        nullif(trim(footnote), '')           as footnote_code,

        safe_cast(start_date as date)        as measure_start_date,
        safe_cast(end_date as date)          as measure_end_date

    from source

)

select * from renamed
