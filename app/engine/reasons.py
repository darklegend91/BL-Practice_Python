"""Named rule identifiers and the templates that turn them into readable text.

Explanations are generated from templates with actual values, never written by
hand per candidate (guide section 6).
"""

from __future__ import annotations

import enum


class Reason(str, enum.Enum):
    # --- hard eligibility ---------------------------------------------------
    OFFLINE_REQUIRED = "OFFLINE_REQUIRED"
    EXTERNAL_PROCESSING_NOT_ALLOWED = "EXTERNAL_PROCESSING_NOT_ALLOWED"
    REGION_UNAVAILABLE = "REGION_UNAVAILABLE"
    ACCESS_TYPE_UNSUPPORTED = "ACCESS_TYPE_UNSUPPORTED"
    COMMERCIAL_USE_NOT_PERMITTED = "COMMERCIAL_USE_NOT_PERMITTED"
    BUDGET_UPFRONT_EXCEEDED = "BUDGET_UPFRONT_EXCEEDED"
    BUDGET_MONTHLY_EXCEEDED = "BUDGET_MONTHLY_EXCEEDED"
    SETUP_EFFORT_EXCEEDED = "SETUP_EFFORT_EXCEEDED"
    VRAM_INSUFFICIENT = "VRAM_INSUFFICIENT"
    SYSTEM_RAM_INSUFFICIENT = "SYSTEM_RAM_INSUFFICIENT"
    CONTEXT_UNSUPPORTED = "CONTEXT_UNSUPPORTED"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    PLAN_LIMIT_BELOW_WORKLOAD = "PLAN_LIMIT_BELOW_WORKLOAD"

    # --- uncertainty (never a satisfied check) ------------------------------
    LICENSE_UNVERIFIED = "LICENSE_UNVERIFIED"
    COMMERCIAL_USE_UNVERIFIED = "COMMERCIAL_USE_UNVERIFIED"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"
    MEMORY_ESTIMATE_APPROXIMATE = "MEMORY_ESTIMATE_APPROXIMATE"
    PERFORMANCE_UNKNOWN = "PERFORMANCE_UNKNOWN"
    POWER_ASSUMED = "POWER_ASSUMED"
    PRICE_STALE = "PRICE_STALE"
    PRICE_MISSING = "PRICE_MISSING"
    SPEC_STALE = "SPEC_STALE"
    SUBSCRIPTION_LIMIT_UNKNOWN = "SUBSCRIPTION_LIMIT_UNKNOWN"
    CONTEXT_SUPPORT_UNKNOWN = "CONTEXT_SUPPORT_UNKNOWN"
    ELECTRICITY_TARIFF_MISSING = "ELECTRICITY_TARIFF_MISSING"
    RESULT_SENSITIVE_TO_ASSUMPTIONS = "RESULT_SENSITIVE_TO_ASSUMPTIONS"
    NO_BREAK_EVEN_IN_HORIZON = "NO_BREAK_EVEN_IN_HORIZON"


TEMPLATES: dict[Reason, str] = {
    Reason.OFFLINE_REQUIRED: (
        "{candidate} sends work to an external service, but this scenario requires "
        "offline operation."
    ),
    Reason.EXTERNAL_PROCESSING_NOT_ALLOWED: (
        "{candidate} processes data externally, which this scenario does not allow."
    ),
    Reason.REGION_UNAVAILABLE: "{candidate} is not documented as available in {region}.",
    Reason.ACCESS_TYPE_UNSUPPORTED: (
        "{candidate} is not documented to support {access_requirement}."
    ),
    Reason.COMMERCIAL_USE_NOT_PERMITTED: (
        "{candidate} does not permit commercial use under {license_name}."
    ),
    Reason.BUDGET_UPFRONT_EXCEEDED: (
        "Upfront cost {upfront} exceeds the upfront budget {budget}."
    ),
    Reason.BUDGET_MONTHLY_EXCEEDED: (
        "Highest monthly cost {monthly} exceeds the monthly budget {budget}."
    ),
    Reason.SETUP_EFFORT_EXCEEDED: (
        "Estimated setup of {setup_hours} h exceeds the {allowance} h available for a "
        "{setup_preference} user."
    ),
    Reason.VRAM_INSUFFICIENT: (
        "{model} needs about {required_gb} GB of GPU memory at {context} tokens and "
        "{concurrency} session(s); {gpu} provides {available_gb} GB."
    ),
    Reason.SYSTEM_RAM_INSUFFICIENT: (
        "{model} needs about {required_gb} GB of system memory; {available_gb} GB is "
        "available. System RAM and GPU VRAM are counted separately."
    ),
    Reason.CONTEXT_UNSUPPORTED: (
        "{candidate} documents at most {supported} context tokens; {requested} were "
        "requested."
    ),
    Reason.CAPABILITY_UNSUPPORTED: "{candidate} is documented as unsuitable for {workload}.",
    Reason.PLAN_LIMIT_BELOW_WORKLOAD: (
        "{candidate} documents {limit} messages per day; the scenario expects "
        "{requested} requests per day."
    ),
    Reason.LICENSE_UNVERIFIED: "The license of {candidate} has not been reviewed.",
    Reason.COMMERCIAL_USE_UNVERIFIED: (
        "Commercial use of {candidate} is not confirmed by reviewed evidence."
    ),
    Reason.CAPABILITY_UNKNOWN: (
        "No reviewed evidence describes {candidate} for {workload}; suitability is "
        "unknown rather than confirmed."
    ),
    Reason.MEMORY_ESTIMATE_APPROXIMATE: (
        "The memory estimate for {model} is approximate because the published "
        "architecture details are incomplete."
    ),
    Reason.PERFORMANCE_UNKNOWN: (
        "No benchmark matches {model} on {gpu} at {context} tokens, so speed is unknown."
    ),
    Reason.POWER_ASSUMED: (
        "Whole-system power for {candidate} is an assumption, not a measurement."
    ),
    Reason.PRICE_STALE: (
        "The price for {candidate} was reviewed on {reviewed_at}, beyond the {max_age} "
        "day freshness policy."
    ),
    Reason.PRICE_MISSING: "No reviewed price exists for {candidate} in {region}.",
    Reason.SPEC_STALE: (
        "Specifications for {candidate} were reviewed on {reviewed_at}, beyond the "
        "{max_age} day freshness policy."
    ),
    Reason.SUBSCRIPTION_LIMIT_UNKNOWN: (
        "{candidate} does not document a usage limit that can be compared with this "
        "workload."
    ),
    Reason.CONTEXT_SUPPORT_UNKNOWN: (
        "The documented context length of {candidate} is unknown."
    ),
    Reason.ELECTRICITY_TARIFF_MISSING: (
        "No electricity tariff was given, so operating cost is unknown rather than zero."
    ),
    Reason.RESULT_SENSITIVE_TO_ASSUMPTIONS: (
        "The leading choice changes between the low, base and high assumption cases."
    ),
    Reason.NO_BREAK_EVEN_IN_HORIZON: (
        "Cumulative cash cost does not cross over within {months} months."
    ),
}


def render(reason: Reason, **values: object) -> str:
    """Fill a reason template. Missing placeholders stay visible rather than crash."""
    template = TEMPLATES[reason]
    try:
        return template.format(**values)
    except KeyError as missing:
        return f"{template} [missing value for {missing.args[0]}]"
