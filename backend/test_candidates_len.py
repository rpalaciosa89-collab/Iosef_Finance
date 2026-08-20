import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Overwrite run_scan logic to print len(new_candidates)
orig_run_scan = server.run_scan

def debug_run_scan(market):
    print("RUNNING RUN_SCAN...")
    res, al = orig_run_scan(market)
    return res, al

server.run_scan = debug_run_scan

# Let's inspect where new_candidates is populated
# We can do this by running it
res, al = server.run_scan("titan100")
