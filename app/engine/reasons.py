"""Every reason the engine can give, and the sentence it turns into.

Codes are stable strings you can branch on; messages are written for a person
and always contain the real numbers.
"""

from __future__ import annotations

# --- reasons that rule an option out ---------------------------------------
OFFLINE_ONLY = "OFFLINE_ONLY"
NOT_IN_YOUR_REGION = "NOT_IN_YOUR_REGION"
NO_API_ACCESS = "NO_API_ACCESS"
COMMERCIAL_USE_NOT_ALLOWED = "COMMERCIAL_USE_NOT_ALLOWED"
NOT_ENOUGH_VRAM = "NOT_ENOUGH_VRAM"
NOT_ENOUGH_SYSTEM_RAM = "NOT_ENOUGH_SYSTEM_RAM"
CONTEXT_TOO_SHORT = "CONTEXT_TOO_SHORT"
NOT_SUITABLE_FOR_WORKLOAD = "NOT_SUITABLE_FOR_WORKLOAD"
DAILY_LIMIT_TOO_LOW = "DAILY_LIMIT_TOO_LOW"
OVER_UPFRONT_BUDGET = "OVER_UPFRONT_BUDGET"
OVER_MONTHLY_BUDGET = "OVER_MONTHLY_BUDGET"
TOO_MUCH_SETUP = "TOO_MUCH_SETUP"
NO_PRICE = "NO_PRICE"

# --- reasons that make an option uncertain rather than impossible -----------
MEMORY_ESTIMATE_APPROXIMATE = "MEMORY_ESTIMATE_APPROXIMATE"
COMMERCIAL_USE_UNKNOWN = "COMMERCIAL_USE_UNKNOWN"
SUITABILITY_UNKNOWN = "SUITABILITY_UNKNOWN"
CONTEXT_LIMIT_UNKNOWN = "CONTEXT_LIMIT_UNKNOWN"
DAILY_LIMIT_UNKNOWN = "DAILY_LIMIT_UNKNOWN"
POWER_IS_ASSUMED = "POWER_IS_ASSUMED"
NO_ELECTRICITY_PRICE = "NO_ELECTRICITY_PRICE"

# --- notes on the result as a whole ----------------------------------------
ANSWER_DEPENDS_ON_ASSUMPTIONS = "ANSWER_DEPENDS_ON_ASSUMPTIONS"
NEVER_PAYS_OFF = "NEVER_PAYS_OFF"
CATALOG_EMPTY = "CATALOG_EMPTY"

UNCERTAIN_CODES = frozenset({
    MEMORY_ESTIMATE_APPROXIMATE, COMMERCIAL_USE_UNKNOWN, SUITABILITY_UNKNOWN,
    CONTEXT_LIMIT_UNKNOWN, DAILY_LIMIT_UNKNOWN, POWER_IS_ASSUMED,
    NO_ELECTRICITY_PRICE,
})

MESSAGES: dict[str, str] = {
    OFFLINE_ONLY:
        "{option} sends your work to someone else's servers, and you asked to stay offline.",
    NOT_IN_YOUR_REGION:
        "{option} is not listed as available in {region}.",
    NO_API_ACCESS:
        "{option} is not documented to let another program call it.",
    COMMERCIAL_USE_NOT_ALLOWED:
        "{option} does not allow commercial use.",
    NOT_ENOUGH_VRAM:
        "{model} needs about {needed} GB of graphics memory for {tokens} tokens "
        "and {sessions} session(s). {machine} has {available} GB.",
    NOT_ENOUGH_SYSTEM_RAM:
        "{model} needs about {needed} GB of system memory and {machine} has "
        "{available} GB. System memory and graphics memory are counted separately.",
    CONTEXT_TOO_SHORT:
        "{option} handles up to {supported} tokens and you asked for {wanted}.",
    NOT_SUITABLE_FOR_WORKLOAD:
        "{option} is not listed as suitable for {workload}.",
    DAILY_LIMIT_TOO_LOW:
        "{option} allows {limit} messages a day and you expect about {wanted}.",
    OVER_UPFRONT_BUDGET:
        "Buying this costs {cost} up front, over your {budget} budget.",
    OVER_MONTHLY_BUDGET:
        "The most expensive month costs {cost}, over your {budget} monthly budget.",
    TOO_MUCH_SETUP:
        "Setting this up takes about {hours} hours and you allowed {allowed}.",
    NO_PRICE:
        "There is no price for {option} in {region}, so it cannot be compared.",
    MEMORY_ESTIMATE_APPROXIMATE:
        "The memory estimate for {model} is rough, because it does not publish "
        "its layer sizes.",
    COMMERCIAL_USE_UNKNOWN:
        "Nobody has confirmed whether {option} allows commercial use.",
    SUITABILITY_UNKNOWN:
        "Nothing on record says whether {option} is good for {workload}.",
    CONTEXT_LIMIT_UNKNOWN:
        "The context limit for {option} is not recorded.",
    DAILY_LIMIT_UNKNOWN:
        "{option} does not publish a daily message limit, so it cannot be "
        "compared with your expected use.",
    POWER_IS_ASSUMED:
        "Power use for {machine} is an assumption, not a measurement.",
    NO_ELECTRICITY_PRICE:
        "You did not give an electricity price, so running cost is unknown "
        "rather than zero.",
    ANSWER_DEPENDS_ON_ASSUMPTIONS:
        "The winner changes between the low, base and high assumptions, so treat "
        "this as close rather than settled.",
    NEVER_PAYS_OFF:
        "Within {months} months the cheaper option never changes.",
    CATALOG_EMPTY:
        "There is nothing in the catalog yet. Run the crawler first.",
}


def say(code: str, **values: object) -> str:
    """Fill in a message. A missing value shows up instead of crashing."""
    try:
        return MESSAGES[code].format(**values)
    except KeyError as missing:
        return f"{MESSAGES.get(code, code)} [missing {missing.args[0]}]"
