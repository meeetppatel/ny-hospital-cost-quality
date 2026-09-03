{{ config(materialized='table') }}

-- MART: one row per NY hospital, cost and quality side by side.
-- This is the analytical table the entire Week 2 analysis sits on.
--
-- Built by joining the three hospital-grain intermediate models on ccn:
--   int_cost_by_hospital         -> volume-weighted avg Medicare payment
--   int_readmissions_by_hospital -> avg excess readmission ratio (headline quality)
--   int_quality_by_hospital      -> HCAHPS star + complication/mortality measures
--
-- Cost is the join spine (a hospital must have Medicare cost data to be in the
-- analysis). Quality measures are LEFT joined -- a hospital may be missing some
-- quality measures (suppressed / not rated), and those stay NULL rather than
-- dropping the hospital. Analysis filters to hospitals with the measures it needs.
--
-- has_core_readmissions flags hospitals with all 3 well-populated readmission
-- conditions (PN/HF/COPD) -- the genuinely comparable set for the headline.

with cost as (
    select * from {{ ref('int_cost_by_hospital') }}
),
readm as (
    select * from {{ ref('int_readmissions_by_hospital') }}
),
qual as (
    select * from {{ ref('int_quality_by_hospital') }}
)

select
    cost.ccn,
    cost.hospital_name,
    cost.state,
    cost.city,
    cost.zip_code,

    -- region classification (for segmentation + the geographic robustness check).
    -- NYC five boroughs vs downstate suburbs (LI + lower Hudson) vs upstate,
    -- by ZIP3 prefix. Medicare per-DRG payment is wage-index adjusted, so region
    -- is a key confound to control when comparing raw cost across the state.
    case
        when substr(cost.zip_code, 1, 3) in ('100','101','102','103','104','111','112','113','114','116') then 'NYC'
        when substr(cost.zip_code, 1, 3) in ('105','106','107','108','109','115','117','118','119') then 'Downstate suburbs'
        else 'Upstate'
    end                                     as region,

    -- cost
    cost.volume_weighted_avg_payment,
    cost.simple_avg_payment,
    cost.total_discharges,
    cost.n_drgs,

    -- headline quality: readmissions
    readm.avg_excess_readmission_ratio,
    readm.readm_pneumonia,
    readm.readm_heart_failure,
    readm.readm_copd,
    (readm.n_core_measures = 3)             as has_core_readmissions,

    -- secondary quality
    qual.hcahps_summary_star,
    qual.patient_safety_psi90,
    qual.mortality_30_pneumonia

from cost
left join readm using (ccn)
left join qual  using (ccn)
