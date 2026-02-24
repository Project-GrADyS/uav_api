#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_FILE="$SCRIPT_DIR/uav-api.service"

if [ "$EUID" -ne 0 ]; then
    echo "Please run with sudo: sudo bash $0"
    exit 1
fi

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: uav-api.service not found at $SERVICE_FILE"
    exit 1
fi

echo "Copying uav-api.service to /etc/systemd/system/ ..."
cp "$SERVICE_FILE" /etc/systemd/system/uav-api.service

echo "Reloading systemd daemon ..."
systemctl daemon-reload

echo "Enabling uav-api service (starts on boot) ..."
systemctl enable uav-api

echo "Starting uav-api service ..."
systemctl start uav-api

echo ""
echo "Service status:"
systemctl status uav-api --no-pager
