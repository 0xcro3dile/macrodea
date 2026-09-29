#!/bin/sh
# Copy board/ onto the board and (re)start the detector as a systemd service.
#
#   ./deploy.sh 192.168.1.50
#
# Logs in as root over ssh. Put your key on the board first
# (ssh-copy-id root@192.168.1.50) or you'll be typing the password twice.
set -e
BOARD=${1:-$BOARD}
if [ -z "$BOARD" ]; then
    echo "usage: ./deploy.sh <board-ip>" >&2
    exit 2
fi
cd "$(dirname "$0")/board"

echo "copying to root@$BOARD:/root/ids ..."
tar -cf - edge_ids.py model.tflite model.json edge-ids.service metrics.py sample_traffic.py |
    ssh root@"$BOARD" '
        set -e
        mkdir -p /root/ids
        tar -xf - -C /root/ids
        mv /root/ids/edge-ids.service /etc/systemd/system/edge-ids.service
        for cmd in python3 mosquitto_pub; do
            command -v $cmd >/dev/null || echo "warning: $cmd is missing on the board"
        done
        systemctl daemon-reload
        systemctl enable --quiet edge-ids
        systemctl restart edge-ids
    '
echo "done, edge-ids is running. Follow it with:"
echo "  ssh root@$BOARD journalctl -u edge-ids -f"
