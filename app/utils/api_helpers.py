import re

def extract_retry_delay(e: Exception, fallback: int = 60) -> int:
    s = str(e)
    m = re.search(r"retry[_\s-]?delay\s*{\s*seconds:\s*(\d+)", s, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"Retry-After:\s*(\d+)", s, re.I)
    if m:
        return int(m.group(1))
    return fallback

def is_429(e: Exception) -> bool:
    s = str(e).lower()
    return ("429" in s) or ("resource exhausted" in s) or ("quota" in s)