import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Let's inspect run_scan's internal new_candidates by reading redis and simulating the loop
from server import TITAN_100, r
import json

new_cands = []
for ticker in TITAN_100:
    lifecycle_key = f"lifecycle:{ticker}"
    state = r.get(lifecycle_key)
    if state:
        state = json.loads(state)
        # Check if it was considered new
        if state.get("signal_status") == "new":
            new_cands.append(ticker)

print("Redis New Candidates:", new_cands)
