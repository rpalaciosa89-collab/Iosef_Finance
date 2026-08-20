import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Let's inspect new_candidates length and contents
results, alerts = server.run_scan("titan100")

# Wait, let's look at what new_candidates actually had.
# We can do this by running a modified scan or importing and calling the sub-parts.
# Actually, let's just print the results of the scan where signal_status is "new"
print("Results with signal_status = new:")
for r in results:
    if r.get("signal_status") == "new":
        print(r["ticker"], r.get("signal_strength_score"))
