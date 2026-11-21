-- Staging model: price transparency -- Rochester General (TALL format)
--
-- Tall files already have payer_name/plan_name as columns, so normalization is
-- mostly renaming into the common target shape shared by all 8 hospitals:
--   ccn, hospital_name, code, code_type, description,
--   payer_name, plan_name, gross_charge, discounted_cash,
--   negotiated_dollar, negotiated_percentage, negotiated_algorithm, ...
--
-- CCN is not present in the file (Finding 10: hospital identity lives in the
-- skipped preamble), so we inject it as a literal from the known source file.
-- These literals get centralized into a hospital dimension seed later.
--
-- Note (data quality): many rows carry no dollar amount at all -- the real
-- price is expressed as a contractual formula in the free-text
-- negotiated_algorithm field (e.g. '74.2% of BC'). We keep those rows but
-- their numeric charge fields are NULL; downstream analysis filters to rows
-- with a real negotiated_dollar or gross_charge.

with source as (

    select * from {{ source('raw', 'price_tx_rochester_general') }}

),

normalized as (

    select
        '330125'                    as ccn,
        'Rochester General Hospital' as hospital_name,

        code_1                      as code,
        code_1_type                 as code_type,
        description,

        billing_class,
        setting,

        payer_name,
        plan_name,

        safe_cast(standard_charge_gross as float64)            as gross_charge,
        safe_cast(standard_charge_discounted_cash as float64)  as discounted_cash_charge,
        safe_cast(standard_charge_negotiated_dollar as float64) as negotiated_dollar,
        safe_cast(standard_charge_negotiated_percentage as float64) as negotiated_percentage,
        standard_charge_negotiated_algorithm                   as negotiated_algorithm,
        standard_charge_methodology                            as methodology

    from source

)

select * from normalized
