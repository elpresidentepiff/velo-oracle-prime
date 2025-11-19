#!/bin/bash
# VÉLØ Oracle v13 - Railway Build Script
# Forces Pydantic v1.10.13 installation and clears dependency cache

set -e

echo "=========================================="
echo "VÉLØ Oracle v13 - Railway Build"
echo "=========================================="

# Clear pip cache to force fresh install
echo "Clearing pip cache..."
pip cache purge || true

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Force install Pydantic v1.10.13 first
echo "Force-installing Pydantic v1.10.13..."
pip install --no-cache-dir --force-reinstall pydantic==1.10.13

# Verify Pydantic version
echo "Verifying Pydantic installation..."
python3.11 -c "import pydantic; print(f'Pydantic version: {pydantic.VERSION}')"

# Install all other dependencies
echo "Installing remaining dependencies..."
pip install --no-cache-dir -r requirements.txt

# Final verification with pip freeze
echo "=========================================="
echo "Final dependency verification:"
echo "=========================================="
pip freeze | grep -i pydantic

echo "=========================================="
echo "Build complete - Pydantic v1.10.13 confirmed"
echo "=========================================="
