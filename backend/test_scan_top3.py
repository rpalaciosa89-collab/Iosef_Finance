import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Let's inspect new_candidates directly
from server import ALL_TICKERS, MARKET_TICKERS
# We can just look at what top_candidates contains by running a tiny slice of run_scan logic
# Or we can write a script that runs it and prints.
