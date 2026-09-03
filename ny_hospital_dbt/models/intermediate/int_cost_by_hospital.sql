-- Intermediate: Medicare inpatient cost aggregated to ONE row per hospital.
--
-- Source grain: one row per hospital per DRG (procedure). We roll up to hospital
-- grain using a VOLUME-WEIGHTED average of avg_total_payment -- each DRG's average
-- payment weighted by its discharge count -- so the result reflects what the
-- hospital actually gets paid across its real case mix, not an unweighted average
-- where a rare expensive procedure counts as much as a common cheap one.
--
-- volume_weighted_avg_payment = sum(avg_total_payment * discharges) / sum(discharges)

with cost as (

    select *
    from {{ ref('stg_medicare_inpatient') }}
    where state = 'NY'
      and avg_total_payment is not null
      and total_discharges is not null
      and total_discharges > 0

)

select
    ccn,
    any_value(hospital_name)                    as hospital_name,
    any_value(state)                            as state,
    any_value(city)                             as city,
    any_value(zip_code)                         as zip_code,
    count(distinct drg_code)                    as n_drgs,
    sum(total_discharges)                       as total_discharges,
    -- volume-weighted average payment (the headline cost measure)
    round(sum(avg_total_payment * total_discharges) / sum(total_discharges), 2)
                                                as volume_weighted_avg_payment,
    -- simple average kept alongside for comparison / robustness checks
    round(avg(avg_total_payment), 2)            as simple_avg_payment,
    round(avg(avg_medicare_payment), 2)         as simple_avg_medicare_payment
from cost
group by ccn
