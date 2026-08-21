-- Staging model: price transparency -- Montefiore Medical Center (TALL format)
-- Same tall-format template as Rochester General. 3.5M rows (largest source).
-- CCN injected as a literal (Finding 10); centralized into a hospital dim later.

with source as (

    select * from {{ source('raw', 'price_tx_montefiore') }}

),

normalized as (

    select
        '330059'                    as ccn,
        'Montefiore Medical Center' as hospital_name,

        code_1                      as code,
        code_1_type                 as code_type,
        description,

        cast(null as string)        as billing_class,  -- not present in this file
        setting,

        payer_name,
        plan_name,

        safe_cast(standard_charge_gross as float64)             as gross_charge,
        safe_cast(standard_charge_discounted_cash as float64)   as discounted_cash_charge,
        safe_cast(standard_charge_negotiated_dollar as float64) as negotiated_dollar,
        safe_cast(standard_charge_negotiated_percentage as float64) as negotiated_percentage,
        standard_charge_negotiated_algorithm                    as negotiated_algorithm,
        standard_charge_methodology                             as methodology

    from source

)

select * from normalized
