def score_domain(domain: str) -> float:
    # Simple MVP scoring: shorter and brandable names score higher.
    name = domain.split(".")[0]
    length_score = max(0, 100 - len(name) * 4)
    vowel_bonus = 6 if any(c in "aeiou" for c in name.lower()) else 0
    digit_penalty = 12 if any(c.isdigit() for c in name) else 0
    return round(max(0.0, min(100.0, length_score + vowel_bonus - digit_penalty)), 2)
