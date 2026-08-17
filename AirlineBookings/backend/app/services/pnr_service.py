import random
import string

# Real airline PNRs avoid ambiguous characters (0/O, 1/I) — do the same.
_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "01OI")


def generate_pnr() -> str:
    return "".join(random.choices(_ALPHABET, k=6))
