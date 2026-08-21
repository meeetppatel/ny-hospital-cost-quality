{{ config(materialized='table') }}

-- Staging model: price transparency -- NewYork-Presbyterian (JSON, multi-campus)
--
-- Landed as one row holding the entire JSON blob in `raw_json`. NYP's structure
-- is richer than Mount Sinai's: payer rates are nested TWO levels deep --
--   standard_charge_information[] -> standard_charges[] -> payers_information[]
-- Each payers_information entry has payer_name, plan_name, standard_charge_dollar,
-- and optionally an algorithm / methodology. So this needs a DOUBLE unnest:
-- one row per (charge, payer-plan), which matches the common long target shape
-- directly (unlike Mount Sinai, whose records mostly carry only gross charges).
--
-- Technique: extract the charge array and unnest it; for each charge, extract
-- standard_charges[0].payers_information[] and unnest that too; then JSON_VALUE
-- the payer-level fields. Materialized as a table (large JSON parse, do it once).
--
-- Note: NYP is a 7-campus system published in one file; the file does not split
-- charges by campus, so all rows share the system-level CCN 330101. This is a
-- known limitation worth a line in the findings doc.

with source as (

    select raw_json from {{ source('raw', 'price_tx_newyork_presbyterian') }}

),

charges as (

    select charge_json
    from source,
    unnest(json_extract_array(raw_json, '$.standard_charge_information')) as charge_json

),

-- pull the first standard_charges entry (setting/min/max live here) and its
-- payers_information array, then unnest payers to one row per payer-plan
charge_payers as (

    select
        charge_json,
        json_value(charge_json, '$.code_information[0].code') as code,
        json_value(charge_json, '$.code_information[0].type') as code_type,
        json_value(charge_json, '$.description')              as description,
        json_value(charge_json, '$.standard_charges[0].setting') as setting,
        payer_json
    from charges,
    unnest(
        coalesce(
            json_extract_array(charge_json, '$.standard_charges[0].payers_information'),
            []
        )
    ) as payer_json

),

final as (

    select
        '330101'                       as ccn,
        'NewYork-Presbyterian Hospital' as hospital_name,

        code,
        code_type,
        description,
        setting,

        json_value(payer_json, '$.payer_name') as payer_name,
        json_value(payer_json, '$.plan_name')  as plan_name,

        safe_cast(json_value(payer_json, '$.standard_charge_dollar') as float64)
            as negotiated_dollar,
        json_value(payer_json, '$.standard_charge_algorithm') as negotiated_algorithm,
        json_value(payer_json, '$.methodology')               as methodology

    from charge_payers

)

select * from final
where negotiated_dollar is not null
   or negotiated_algorithm is not null
