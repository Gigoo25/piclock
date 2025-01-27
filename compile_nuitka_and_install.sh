#!/bin/bash

# Compile the Python script with Nuitka
echo "Compiling piclock.py with Nuitka..."
python3 -m nuitka --standalone --onefile --include-data-dir=templates=templates --include-data-dir=static=static --assume-yes-for-downloads --output-dir=build piclock.py

# Check if the compilation was successful
if [ $? -eq 0 ]; then
    echo "Compilation successful."

    # Move the compiled file to the permanent location
    echo "Moving compiled binary to /usr/local/bin..."
    sudo cp build/piclock.bin /usr/local/bin/piclock.bin

    # Give execute permissions to the binary
    echo "Giving execute permissions to piclock.bin..."
    sudo chmod +x /usr/local/bin/piclock.bin

    # Move the service file to the permanent location
    echo "Moving service file to /etc/systemd/system..."
    sudo cp piclock.service /etc/systemd/system/piclock.service

    # Reload the systemd manager configuration
    echo "Reloading systemd manager configuration..."
    sudo systemctl daemon-reload

    # Ensure the service is enabled
    echo "Enabling piclock.service..."
    sudo systemctl enable piclock.service

    # Start the service
    echo "Starting piclock.service..."
    sudo systemctl start piclock.service

    echo "PiClock service has been installed and started successfully."
else
    echo "Compilation failed. Please check the error messages above."
fi