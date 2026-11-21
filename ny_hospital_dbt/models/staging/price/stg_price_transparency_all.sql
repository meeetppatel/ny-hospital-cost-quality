{{ config(materialized='table') }}

-- Unified staging model: all 8 hospitals' price transparency data in ONE table
-- with ONE strict schema.
--
-- WHY THIS EXISTS: an audit found the 8 per-hospital price staging models did
-- NOT share identical columns -- tall models have billing_class/payer_name/
-- plan_name; wide models have payer_plan and no billing_class; the JSON models
-- vary again (Mount Sinai gross-charge only; NYP missing gross/billing_class).
-- A naive UNION of them would fail or misalign. This model enforces one 13-column
-- contract by explicitly selecting the same columns from each source, filling
-- gaps with typed NULLs, and folding the wide-format payer_plan label into
-- plan_name (payer_name left NULL -- payer|plan boundary was lost at load,
-- Finding 8). Materialized as a table (reads NYU's 4M-row table + 2 JSON tables).
--
-- Common contract:
--   source_hospital, ccn, hospital_name, code, code_type, description, setting,
--   payer_name, plan_name, gross_charge, discounted_cash_charge,
--   negotiated_dollar, negotiated_algorithm

with tall_rochester as (
    select 'rochester_general' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, payer_name, plan_name,
           gross_charge, discounted_cash_charge, negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_rochester_general') }}
),
tall_montefiore as (
    select 'montefiore' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, payer_name, plan_name,
           gross_charge, discounted_cash_charge, negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_montefiore') }}
),

-- wide models: no billing_class; payer_plan holds the full payer|plan label,
-- which we map into plan_name (payer_name NULL).
wide_brooklyn as (
    select 'brooklyn_hospital' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, cast(null as string) as payer_name, payer_plan as plan_name,
           gross_charge, discounted_cash_charge, negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_brooklyn_hospital') }}
),
wide_flushing as (
    select 'flushing_hospital' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, cast(null as string) as payer_name, payer_plan as plan_name,
           gross_charge, discounted_cash_charge, negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_flushing_hospital') }}
),
wide_albany as (
    select 'albany_medical' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, cast(null as string) as payer_name, payer_plan as plan_name,
           gross_charge, discounted_cash_charge, negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_albany_medical') }}
),
wide_nyu as (
    select 'nyu_langone' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, cast(null as string) as payer_name, payer_plan as plan_name,
           gross_charge, discounted_cash_charge, negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_nyu_langone') }}
),

-- JSON models: fill whatever columns they lack with typed NULLs.
json_mount_sinai as (
    select 'mount_sinai' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting,
           cast(null as string) as payer_name, cast(null as string) as plan_name,
           gross_charge, discounted_cash_charge,
           cast(null as float64) as negotiated_dollar, cast(null as string) as negotiated_algorithm
    from {{ ref('stg_price_tx_mount_sinai') }}
),
json_nyp as (
    select 'newyork_presbyterian' as source_hospital, ccn, hospital_name, code, code_type,
           description, setting, payer_name, plan_name,
           cast(null as float64) as gross_charge, cast(null as float64) as discounted_cash_charge,
           negotiated_dollar, negotiated_algorithm
    from {{ ref('stg_price_tx_newyork_presbyterian') }}
)

select * from tall_rochester
union all select * from tall_montefiore
union all select * from wide_brooklyn
union all select * from wide_flushing
union all select * from wide_albany
union all select * from wide_nyu
union all select * from json_mount_sinai
union all select * from json_nyp
