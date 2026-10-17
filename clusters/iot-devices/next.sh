#!/bin/sh

CONTAINER="${1:-iot-1}"

docker exec "$CONTAINER" sh -c 'touch /control/next' || {
    echo "Failed to send NEXT command to $CONTAINER" >&2
    exit 1
}

echo "NEXT command sent to $CONTAINER"
