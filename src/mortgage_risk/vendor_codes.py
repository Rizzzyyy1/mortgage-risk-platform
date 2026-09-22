"""SF historical code domains: Fannie Mae glossary 2026-09-10, PDF page 4."""
import re
SF_ZERO_CODES = frozenset({'01','02','03','06','09','15','16','96'})
def code_issue(field, value):
    value = (value or '').strip()
    if not value:
        return None  # Missingness is evaluated separately; never imputed.
    if field == 'delinquency_status':
        return None if value == 'XX' or re.fullmatch(r'[0-9]{2}', value) else 'unsupported'
    if field == 'modification_flag':
        return None if value in {'Y','N'} else 'unsupported'
    if field == 'zero_balance_code':
        return None if value in SF_ZERO_CODES else 'unsupported_for_sf_historical'
    raise ValueError(field)
