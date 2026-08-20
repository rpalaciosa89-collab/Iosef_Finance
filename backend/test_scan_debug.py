import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Let's inspect run_scan's new_candidates directly by hooking into new_candidates.append
orig_run_scan = server.run_scan

def debug_run_scan(market):
    print("DEBUG RUN SCAN CALLED FOR:", market)
    return orig_run_scan(market)

server.run_scan = debug_run_scan

results, alerts = server.run_scan("titan100")
print("Scan returned", len(results), "results")
