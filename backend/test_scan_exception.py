import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Overwrite the try/except block behavior by replacing execute_trade with a version that prints exceptions
orig_execute = server.execute_trade

def debug_execute(user_id, payload, db):
    print(f"CALLING EXECUTE_TRADE FOR {payload.ticker}...")
    try:
        res = orig_execute(user_id, payload, db)
        print(f"SUCCESS EXECUTE_TRADE FOR {payload.ticker}!")
        return res
    except Exception as e:
        print(f"EXCEPTION EXECUTE_TRADE FOR {payload.ticker}: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        raise e

server.execute_trade = debug_execute

try:
    results, alerts = server.run_scan("titan100")
except Exception as e:
    print(f"RUN_SCAN CRASHED: {e}")
