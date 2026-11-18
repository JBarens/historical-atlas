"""Create one invite code for live mode and print it with its sha256 hash.

Run: uv run python backend/scripts/make_invite_code.py [label]
The code is printed once to this terminal and not stored anywhere. Add "label:hash" to the INVITE_CODES_SHA256
secret (comma-separated) and send the code to the person.
"""
import hashlib
import secrets
import sys

label = (sys.argv[1] if len(sys.argv) > 1 else "guest").replace(",", "").replace(":", "")
code = "-".join(secrets.token_hex(3) for _ in range(3))
h = hashlib.sha256(code.encode()).hexdigest()
print(f"code (give this to {label}; shown once): {code}")
print(f"secret entry: {label}:{h}")
