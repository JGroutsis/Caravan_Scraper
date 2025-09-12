def norm(s: str) -> str:
    return ''.join(ch.lower() for ch in s if ch.isalnum() or ch.isspace()).strip()
