-- Intermediate: readmissions aggregated to ONE row per hospital.
--
-- Source grain: one row per hospital per condition-specific measure (PN, HF,
-- COPD, AMI, HIP-KNEE, CABG). We average each hospital's populated excess
-- readmission ratios across whatever conditions it reports (ignoring suppressed
-- rows). Excess readmission ratio > 1.0 = worse than expected; < 1.0 = better.
--
-- We also flag whether the hospital has the 3 well-populated CORE measures
-- (pneumonia, heart failure, COPD), so the analysis can restrict to hospitals
-- that are genuinely comparable rather than those rated on only a rare surgery.

with readm as (

    select *
    from {{ ref('stg_hospital_readmissions') }}
    where state = 'NY'
      and not is_suppressed
      and excess_readmission_ratio is not null

)

select
    ccn,
    any_value(hospital_name)                                as hospital_name,
    count(distinct measure_name)                            as n_measures,
    round(avg(excess_readmission_ratio), 4)                 as avg_excess_readmission_ratio,
    -- core-measure coverage flag (PN + HF + COPD all present)
    countif(measure_name in ('READM-30-PN-HRRP','READM-30-HF-HRRP','READM-30-COPD-HRRP'))
                                                            as n_core_measures,
    -- individual condition ratios kept for drill-down
    round(avg(case when measure_name='READM-30-PN-HRRP'  then excess_readmission_ratio end), 4) as readm_pneumonia,
    round(avg(case when measure_name='READM-30-HF-HRRP'  then excess_readmission_ratio end), 4) as readm_heart_failure,
    round(avg(case when measure_name='READM-30-COPD-HRRP' then excess_readmission_ratio end), 4) as readm_copd
from readm
group by ccn
