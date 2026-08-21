-- Staging model: CMS Hospital Readmissions Reduction Program
--
-- Staging does ONLY: rename to consistent names, cast types, map suppression
-- placeholders to NULL. No joins, no business logic -- that is the marts layer.
--
-- Directly implements the "planned handling" from docs/data_quality_findings.md:
--   Finding 1/2: rename facility_id -> ccn (the CCN is the cross-source join key)
--   Finding 4:   'N/A' in numeric columns -> NULL via SAFE_CAST, plus is_suppressed flag
--   Finding 5:   footnote code preserved to justify why rows are suppressed

with source as (

    select * from {{ source('raw', 'hospital_readmissions') }}

),

renamed as (

    select
        -- identifiers (Finding 1/2: standardize the join key name to ccn)
        facility_id                                   as ccn,
        facility_name                                 as hospital_name,
        state,

        -- measure this row describes (e.g. READM-30-AMI-HRRP)
        measure_name,

        -- numeric measures: SAFE_CAST turns non-numeric suppression
        -- placeholders like 'N/A' into NULL instead of erroring (Finding 4)
        safe_cast(number_of_discharges as int64)      as number_of_discharges,
        safe_cast(excess_readmission_ratio as float64) as excess_readmission_ratio,
        safe_cast(predicted_readmission_rate as float64) as predicted_readmission_rate,
        safe_cast(expected_readmission_rate as float64) as expected_readmission_rate,
        safe_cast(number_of_readmissions as int64)    as number_of_readmissions,

        -- suppression handling made explicit and analyzable (Finding 4/5):
        -- flag rows where the headline ratio is suppressed, and keep the
        -- footnote code that explains WHY it was suppressed.
        case
            when excess_readmission_ratio is null
                 or trim(excess_readmission_ratio) in ('N/A', 'Not Available', '')
            then true
            else false
        end                                           as is_suppressed,
        nullif(trim(footnote), '')                    as footnote_code,

        -- reporting period
        safe_cast(start_date as date)                 as measure_start_date,
        safe_cast(end_date as date)                   as measure_end_date

    from source

)

select * from renamed
