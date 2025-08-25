#!/bin/bash

# PiClock Service Uninstallation Script

set -e

echo "=== PiClock Service Uninstallation ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script as root (use sudo)"
    exit 1
fi

# Stop the service if running
echo "Stopping PiClock service..."
systemctl stop piclock.service 2>/dev/null || true

# Disable the service
echo "Disabling PiClock service..."
systemctl disable piclock.service 2>/dev/null || true

# Remove service file
echo "Removing service file..."
rm -f /etc/systemd/system/piclock.service

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

echo ""
echo "=== Uninstallation Complete ==="
echo "PiClock service has been removed."
