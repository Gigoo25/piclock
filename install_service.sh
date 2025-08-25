#!/bin/bash

# PiClock Service Installation Script
# This script installs PiClock as a systemd service

set -e

echo "=== PiClock Service Installation ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script as root (use sudo)"
    exit 1
fi

# Get the current user (who invoked sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
echo "Installing service for user: $ACTUAL_USER"

# Get the current directory (where the script is run from)
CURRENT_DIR=$(pwd)
echo "Installing from directory: $CURRENT_DIR"

# Check if required files exist
if [ ! -f "$CURRENT_DIR/piclock.py" ]; then
    echo "Error: piclock.py not found in current directory"
    exit 1
fi

if [ ! -f "$CURRENT_DIR/requirements.txt" ]; then
    echo "Warning: requirements.txt not found. Make sure dependencies are installed."
fi

echo "Found required files in $CURRENT_DIR"

# Update service file with correct user and paths
sed -i "s|User=pi|User=$ACTUAL_USER|g" piclock.service
sed -i "s|Group=pi|Group=$ACTUAL_USER|g" piclock.service
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$CURRENT_DIR|g" piclock.service

# Check for virtual environment and use appropriate Python interpreter
if [ -d "$CURRENT_DIR/.venv" ]; then
    echo "Virtual environment detected, using .venv/bin/python"
    sed -i "s|ExecStart=.*|ExecStart=$CURRENT_DIR/.venv/bin/python $CURRENT_DIR/piclock.py|g" piclock.service
else
    echo "No virtual environment detected, using system Python"
    sed -i "s|ExecStart=.*|ExecStart=/usr/bin/python3 $CURRENT_DIR/piclock.py|g" piclock.service
fi

sed -i "s|ReadWritePaths=.*|ReadWritePaths=$CURRENT_DIR|g" piclock.service

# Copy service file to systemd directory
echo "Installing systemd service file..."
cp piclock.service /etc/systemd/system/

# Reload systemd to recognize new service
echo "Reloading systemd..."
systemctl daemon-reload

# Enable GPIO access for the user
echo "Setting up GPIO permissions..."
usermod -a -G gpio $ACTUAL_USER

# Set GPIO device permissions
if [ -e /dev/gpiomem ]; then
    chmod 666 /dev/gpiomem
    echo "GPIO memory device permissions set"
fi

# Check if Python dependencies are installed
echo "Checking Python dependencies..."
if [ -f "$CURRENT_DIR/requirements.txt" ]; then
    # Check for virtual environment
    if [ -d "$CURRENT_DIR/.venv" ]; then
        echo "Virtual environment detected at $CURRENT_DIR/.venv"
        echo "Installing dependencies in virtual environment..."
        if [ -f "$CURRENT_DIR/.venv/bin/pip" ]; then
            "$CURRENT_DIR/.venv/bin/pip" install -r "$CURRENT_DIR/requirements.txt"
            echo "Dependencies installed successfully in virtual environment."
        else
            echo "Warning: Virtual environment found but pip not available."
            echo "Please activate the virtual environment and run: pip install -r requirements.txt"
        fi
    else
        echo "No virtual environment detected."
        echo "Please install dependencies manually or create a virtual environment."
        echo "To create a virtual environment: python3 -m venv .venv"
        echo "Then activate it and run: pip install -r requirements.txt"
    fi
else
    echo "No requirements.txt found. Please ensure all dependencies are installed manually."
fi

# Enable the service to start on boot
echo "Enabling PiClock service..."
systemctl enable piclock.service

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Service commands:"
echo "  Start:   sudo systemctl start piclock"
echo "  Stop:    sudo systemctl stop piclock"
echo "  Status:  sudo systemctl status piclock"
echo "  Logs:    sudo journalctl -u piclock -f"
echo ""
echo "The service will start automatically on boot."
echo "To start it now, run: sudo systemctl start piclock"
echo ""
echo "Note: You may need to log out and back in for GPIO group membership to take effect."
