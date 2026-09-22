WITH base AS (
    SELECT
        loan_id,
        reporting_month,
        current_actual_upb,
        original_upb,
        COALESCE(NULLIF(TRIM(delinquency_status), ''), 'missing') AS delinquency_category,
        COALESCE(NULLIF(TRIM(modification_flag), ''), 'missing') AS modification_flag_value,
        COALESCE(NULLIF(TRIM(zero_balance_code), ''), 'missing') AS termination_code,
        CASE WHEN current_actual_upb IS NULL THEN 1 ELSE 0 END AS is_missing_balance,
        CASE WHEN current_actual_upb = 0 THEN 1 ELSE 0 END AS is_zero_balance,
        CASE WHEN current_actual_upb IS NOT NULL THEN 1 ELSE 0 END AS is_known_balance
    FROM sample_monthly
),
monthly_summary AS (
    SELECT
        reporting_month,
        COUNT(DISTINCT loan_id) AS observed_loan_count,
        COUNT(DISTINCT CASE WHEN current_actual_upb IS NOT NULL THEN loan_id END) AS loans_with_known_current_balance,
        COUNT(DISTINCT CASE WHEN current_actual_upb IS NULL THEN loan_id END) AS loans_with_missing_current_balance,
        COUNT(DISTINCT CASE WHEN current_actual_upb = 0 THEN loan_id END) AS loans_with_zero_current_balance,
        SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS total_known_current_balance,
        AVG(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb END) AS avg_known_current_balance,
        SUM(CASE WHEN current_actual_upb IS NOT NULL THEN 1 ELSE 0 END) AS known_balance_record_count,
        COUNT(*) AS observed_record_count
    FROM base
    GROUP BY reporting_month
    ORDER BY reporting_month
),
monthly_delinq AS (
    SELECT
        reporting_month,
        delinquency_category,
        COUNT(DISTINCT loan_id) AS observed_loans,
        SUM(CASE WHEN current_actual_upb IS NOT NULL THEN 1 ELSE 0 END) AS loans_with_known_balance,
        SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS known_balance_total
    FROM base
    GROUP BY reporting_month, delinquency_category
    ORDER BY reporting_month, delinquency_category
),
monthly_mod AS (
    SELECT
        reporting_month,
        modification_flag_value AS modification_flag,
        COUNT(DISTINCT loan_id) AS observed_loans,
        SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS known_balance_total
    FROM base
    GROUP BY reporting_month, modification_flag_value
    ORDER BY reporting_month, modification_flag_value
),
month_term AS (
    SELECT
        reporting_month,
        termination_code AS zero_balance_code,
        COUNT(DISTINCT loan_id) AS observed_loans,
        SUM(CASE WHEN current_actual_upb IS NOT NULL THEN current_actual_upb ELSE 0 END) AS known_balance_total
    FROM base
    GROUP BY reporting_month, termination_code
    ORDER BY reporting_month, termination_code
)
SELECT
    'monthly_summary' AS result_type,
    *
FROM monthly_summary
UNION ALL
SELECT
    'delinquency_detail' AS result_type,
    reporting_month,
    NULL::BIGINT AS observed_loan_count,
    NULL::BIGINT AS loans_with_known_current_balance,
    NULL::BIGINT AS loans_with_missing_current_balance,
    NULL::BIGINT AS loans_with_zero_current_balance,
    NULL::DECIMAL(18,2) AS total_known_current_balance,
    NULL::DOUBLE AS avg_known_current_balance,
    NULL::BIGINT AS known_balance_record_count,
    NULL::BIGINT AS observed_record_count,
    delinquency_category AS delinquency_category,
    observed_loans,
    loans_with_known_balance,
    0 AS missing_count,
    0 AS zero_count,
    known_balance_total
FROM monthly_delinq
UNION ALL
SELECT
    'modification_detail' AS result_type,
    reporting_month,
    NULL::BIGINT AS observed_loan_count,
    NULL::BIGINT AS loans_with_known_current_balance,
    NULL::BIGINT AS loans_with_missing_current_balance,
    NULL::BIGINT AS loans_with_zero_current_balance,
    NULL::DECIMAL(18,2) AS total_known_current_balance,
    NULL::DOUBLE AS avg_known_current_balance,
    NULL::BIGINT AS known_balance_record_count,
    NULL::BIGINT AS observed_record_count,
    modification_flag AS delinquency_category,
    observed_loans,
    NULL::BIGINT AS loans_with_known_balance,
    0 AS missing_count,
    0 AS zero_count,
    known_balance_total
FROM monthly_mod
UNION ALL
SELECT
    'termination_detail' AS result_type,
    reporting_month,
    NULL::BIGINT AS observed_loan_count,
    NULL::BIGINT AS loans_with_known_current_balance,
    NULL::BIGINT AS loans_with_missing_current_balance,
    NULL::BIGINT AS loans_with_zero_current_balance,
    NULL::DECIMAL(18,2) AS total_known_current_balance,
    NULL::DOUBLE AS avg_known_current_balance,
    NULL::BIGINT AS known_balance_record_count,
    NULL::BIGINT AS observed_record_count,
    zero_balance_code AS delinquency_category,
    observed_loans,
    NULL::BIGINT AS loans_with_known_balance,
    0 AS missing_count,
    0 AS zero_count,
    known_balance_total
FROM month_term
ORDER BY result_type, reporting_month, delinquency_category;
