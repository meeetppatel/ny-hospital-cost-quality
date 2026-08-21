{{ config(materialized='table') }}

-- Staging model: price transparency -- The Mount Sinai Hospital (JSON format)
--
-- Landed as a single row holding the entire ~172MB JSON blob in `raw_json`.
-- The charge records live in the nested `standard_charge_information` array,
-- each with: description, code_information[] ({code,type}), standard_charges[]
-- ({gross_charge, discounted_cash, setting, billing_class}), and optionally
-- payers_information[] (negotiated rates). Some records have no payer rates.
--
-- Technique: JSON_EXTRACT_ARRAY splits the big array into elements, UNNEST turns
-- them into rows, then JSON_VALUE pulls scalar fields. We take the FIRST
-- code_information entry as the primary code (a charge can map to several code
-- systems; primary is sufficient for cross-hospital comparison). Materialized as
-- a table because parsing a 172MB JSON cell on every read would be wasteful.
--
-- Reaches the common target shape: ccn, hospital_name, code, code_type,
-- description, gross_charge, discounted_cash_charge, etc. Mount Sinai's first
-- standard_charges entry is used for the charge fields.

with source as (

    select raw_json from {{ source('raw', 'price_tx_mount_sinai') }}

),

charges as (

    select
        charge_json
    from source,
    unnest(json_extract_array(raw_json, '$.standard_charge_information')) as charge_json

),

final as (

    select
        '330024'                  as ccn,
        'The Mount Sinai Hospital' as hospital_name,

        -- primary code = first element of code_information[]
        json_value(charge_json, '$.code_information[0].code')  as code,
        json_value(charge_json, '$.code_information[0].type')  as code_type,
        json_value(charge_json, '$.description')               as description,

        json_value(charge_json, '$.standard_charges[0].setting')       as setting,
        json_value(charge_json, '$.standard_charges[0].billing_class') as billing_class,

        safe_cast(json_value(charge_json, '$.standard_charges[0].gross_charge') as float64)
            as gross_charge,
        safe_cast(json_value(charge_json, '$.standard_charges[0].discounted_cash') as float64)
            as discounted_cash_charge

    from charges

)

select * from final
