-- Staging model: CMS HCAHPS patient satisfaction survey
-- Recall from profiling: ~87% of rows are 'Not Applicable' and another slice
-- 'Not Available' -- under 9% carry a usable star rating. We do NOT drop those
-- rows here (staging preserves grain); we flag them so the marts layer can
-- filter deliberately. star rating is 1-5; percent/linear-mean are the
-- underlying measures.

with source as (

    select * from {{ source('raw', 'hospital_hcahps') }}

),

renamed as (

    select
        facility_id                              as ccn,
        facility_name                            as hospital_name,
        state,
        citytown                                 as city,
        zip_code,

        hcahps_measure_id                        as measure_id,
        hcahps_question                          as question,
        hcahps_answer_description                as answer_description,

        -- star rating: 'Not Applicable' / 'Not Available' -> NULL
        safe_cast(patient_survey_star_rating as int64) as star_rating,
        safe_cast(hcahps_answer_percent as float64)    as answer_percent,
        safe_cast(hcahps_linear_mean_value as float64) as linear_mean_value,
        safe_cast(number_of_completed_surveys as int64) as completed_surveys,
        safe_cast(survey_response_rate_percent as float64) as response_rate_percent,

        -- a row is "usable" only when it carries a real star rating
        case
            when patient_survey_star_rating is null
                 or trim(patient_survey_star_rating) in ('Not Applicable', 'Not Available', 'N/A', '')
            then true
            else false
        end                                      as is_suppressed,
        nullif(trim(patient_survey_star_rating_footnote), '') as star_rating_footnote,

        safe_cast(start_date as date)            as measure_start_date,
        safe_cast(end_date as date)              as measure_end_date

    from source

)

select * from renamed
