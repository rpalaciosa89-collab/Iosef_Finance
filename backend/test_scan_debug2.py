import sys, os
sys.path.append(os.path.abspath('.'))

import server
from app.models.user import User

# Let's run a modified version of the scan loop just to extract top_candidates
results, alerts = server.run_scan("titan100")

# Wait, we can just fetch all candidates from Redis lifecycle to see what is stored!
import redis
r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
keys = r.keys("lifecycle:*")
for k in keys:
    print(k, r.get(k))
