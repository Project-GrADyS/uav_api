#!/bin/bash

# Ensure script is run with root privileges
if [ "$EUID" -ne 0 ]; then
    echo "Error: Please run with sudo: sudo bash $0 <sysid> <gradys_gs_ip>"
    exit 1
fi

# Validate arguments
SYSID="$1"
GRADYS_GS_IP="$2"

if [ -z "$SYSID" ] || [ -z "$GRADYS_GS_IP" ]; then
    echo "Error: Missing required arguments."
    echo "Usage: sudo bash $0 <sysid> <gradys_gs_ip>"
    echo "Example: sudo bash $0 1 10.0.2.255:8000"
    exit 1
fi

# Calculate dynamic API port based on sysid
API_PORT=$((8000 + SYSID))

CONFIG_DIR="/etc/uavs"
CONFIG_FILE="$CONFIG_DIR/default.ini"
SERVICE_PATH="/etc/systemd/system/uav-api.service"

echo "=== 1. Writing UAV Configuration to $CONFIG_FILE ==="
mkdir -p "$CONFIG_DIR"

cat <<EOF > "$CONFIG_FILE"
[api]
port = ${API_PORT}
uav_connection = 127.0.0.1:17171
connection_type = udpin
sysid = ${SYSID}
gradys_gs = ${GRADYS_GS_IP}
scripts_path = /home/pi/uav_scripts
EOF

echo "Configuration generated successfully."

echo "=== 2. Creating systemd service file at $SERVICE_PATH ==="
cat <<EOF > "$SERVICE_PATH"
[Unit]
Description=UAV API - ArduPilot MAVLink HTTP REST API
After=network.target

[Service]
Type=simple
User=pi
Environment=PATH=/home/pi/.venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/pi/.venv/bin/uav-api --config $CONFIG_FILE
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "=== 3. Configuring and starting systemd service ==="
systemctl daemon-reload
systemctl enable uav-api.service

# Restart if service is already running, otherwise start it fresh
if systemctl is-active --quiet uav-api; then
    echo "Service is currently active. Restarting to apply new configuration..."
    systemctl restart uav-api
else
    echo "Starting uav-api service..."
    systemctl start uav-api
fi

echo ""
echo "=== Service Status ==="
systemctl status uav-api --no-pager