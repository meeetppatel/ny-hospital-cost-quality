-- Staging model: CMS Medicare Inpatient Utilization & Payment (COST data)
-- This is the cost side of the analysis. Rename the verbose Rndrng_Prvdr_*
-- fields to clean names; crucially rename Rndrng_Prvdr_CCN -> ccn so it joins
-- to the quality staging models (Finding 1/2). One row per hospital per DRG
-- (procedure group).

with source as (

    select * from {{ source('raw', 'medicare_inpatient_utilization') }}

),

renamed as (

    select
        Rndrng_Prvdr_CCN                        as ccn,
        Rndrng_Prvdr_Org_Name                   as hospital_name,
        Rndrng_Prvdr_City                       as city,
        Rndrng_Prvdr_State_Abrvtn               as state,
        Rndrng_Prvdr_Zip5                       as zip_code,
        Rndrng_Prvdr_RUCA_Desc                  as rural_urban_desc,

        DRG_Cd                                  as drg_code,
        DRG_Desc                                as drg_description,

        -- cost/volume measures. These come clean (no suppression placeholders
        -- observed) but SAFE_CAST anyway for safety.
        safe_cast(Tot_Dschrgs as int64)         as total_discharges,
        safe_cast(Avg_Submtd_Cvrd_Chrg as float64) as avg_submitted_charge,
        safe_cast(Avg_Tot_Pymt_Amt as float64)  as avg_total_payment,
        safe_cast(Avg_Mdcr_Pymt_Amt as float64) as avg_medicare_payment

    from source

)

select * from renamed
