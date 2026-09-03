-- Intermediate: patient experience + clinical outcome quality, one row per hospital.
--
-- HCAHPS: we take ONLY the summary star rating row (measure_id = 'H_STAR_RATING',
-- "Summary star rating") -- the single overall patient-experience score per
-- hospital -- rather than averaging unrelated survey sub-dimensions.
--
-- Complications: we surface two clear clinical measures as secondary outcomes:
--   PSI_90  = composite patient-safety indicator (lower = safer)
--   MORT_30_PN = 30-day pneumonia mortality rate (lower = better)
-- Kept secondary; readmission ratio (separate model) anchors the headline finding.

with hcahps_star as (

    select
        ccn,
        any_value(hospital_name)                as hospital_name,
        max(star_rating)                        as hcahps_summary_star
    from {{ ref('stg_hospital_hcahps') }}
    where state = 'NY'
      and measure_id = 'H_STAR_RATING'
      and star_rating is not null
    group by ccn

),

complications as (

    select
        ccn,
        round(avg(case when measure_id = 'PSI_90'     then score end), 4) as patient_safety_psi90,
        round(avg(case when measure_id = 'MORT_30_PN' then score end), 4) as mortality_30_pneumonia
    from {{ ref('stg_hospital_complications') }}
    where state = 'NY'
      and not is_suppressed
      and score is not null
    group by ccn

)

select
    coalesce(h.ccn, c.ccn)          as ccn,
    h.hospital_name,
    h.hcahps_summary_star,
    c.patient_safety_psi90,
    c.mortality_30_pneumonia
from hcahps_star h
full outer join complications c using (ccn)
