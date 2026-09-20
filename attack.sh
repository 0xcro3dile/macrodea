#!/bin/sh
# One-command attacker for Linux/macOS teammates. Adds the route (if missing) then attacks.
#   ./attack.sh scan     (or: flood | bruteforce | slowloris | normal)
BOARD=10.42.0.208
GW=10.40.58.21
if command -v ip >/dev/null 2>&1; then           # Linux
    ip route get "$BOARD" 2>/dev/null | grep -q "via $GW" || sudo ip route add 10.42.0.0/24 via "$GW"
else                                              # macOS
    route -n get "$BOARD" 2>/dev/null | grep -q "$GW" || sudo route -n add 10.42.0.0/24 "$GW"
fi
echo "route ready -> attacking $BOARD with '${1:-scan}'"
python3 simulate.py "$BOARD" "${1:-scan}"
