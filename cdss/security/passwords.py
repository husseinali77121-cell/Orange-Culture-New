# © 2025 Dr / Hussein Ali -- Orange Lab, 6 October City, Egypt
# Microbiology CDSS -- All Rights Reserved
"""PBKDF2 password hashing and constant-time verification."""
import base64
import hashlib
import hmac
import os




# ═══════════════════════════════════════════════════════════════════════
# PASSWORD VERIFICATION
# ----------------------------------------------------------------------
# The commercial build authenticated on an EMAIL ADDRESS ALONE. Anyone who knew
# or guessed a subscriber's address had full access to a paid product, and there
# was no way for a customer to revoke a leaked login short of deleting the
# account. Email is an identifier, not a secret.
#
# Rollout is deliberately backward-compatible so no existing customer is locked
# out on deploy:
#   * secrets["subscriber_hashes"] = {"<email>": "pbkdf2_sha256$<iters>$<salt>$<hash>"}
#   * an email WITH a hash must supply the matching password
#   * an email WITHOUT a hash still logs in as before, but the account is listed
#     in get_startup_validation_issues() so the gap is visible rather than silent
#
# Generate a hash with:  python -c "import streamlit_app as a; \
#                                   print(a.make_password_hash('the-password'))"
# ═══════════════════════════════════════════════════════════════════════
_PBKDF2_ITERATIONS = 240_000

# The two aliases that used to live here (_LOGIN_MAX_ATTEMPTS,
# _LOGIN_LOCKOUT_SECONDS) were kept for backward compatibility when the throttle
# moved to auth_service.py, and nothing ever read them. Read
# _AUTH.MAX_ATTEMPTS / _AUTH.LOCKOUT_SECONDS directly — one name per fact.


# ── Administrator utility — intentionally not called from anywhere ──────────
# make_password_hash() is run BY HAND, from a Python shell, to generate the
# value that goes into the `subscriber_hashes` secret:
#
#     python -c "import streamlit_app as s; print(s.make_password_hash('...'))"
#
# A dead-code scan flags it every time because nothing in the app invokes it.
# It stays: an operator needs it to onboard a subscriber, and the alternative
# is a password-hashing routine pasted into a shell from memory, which is how
# salts get omitted. Deleting it would remove the only correct way to produce
# the value this app refuses to start without.
def make_password_hash(password: str, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Encode a password as pbkdf2_sha256$iterations$salt$hash (base64 parts)."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )

def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of a password against a stored pbkdf2 record."""
    try:
        algo, iters, salt_b64, hash_b64 = str(encoded).split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", (password or "").encode("utf-8"),
            base64.b64decode(salt_b64), int(iters),
        )
        return hmac.compare_digest(dk, base64.b64decode(hash_b64))
    except Exception:
        return False
