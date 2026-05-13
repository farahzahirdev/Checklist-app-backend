#!/bin/bash
# Fix admin@example.com user - setup and execution script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Fix admin@example.com User Script"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please activate your virtual environment first:"
    echo "   source venv/bin/activate"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create .env file with DATABASE_URL and other required variables"
    exit 1
fi

echo "✅ Environment ready"
echo ""

# Run the Python script
echo "Running fix script..."
echo ""

python3 fix_admin_user.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS!"
    echo "The admin@example.com user has been fixed."
    echo ""
    echo "Next steps:"
    echo "1. Restart your backend application"
    echo "2. Log in to verify the fix"
    echo "3. Check that admin dashboard is accessible"
else
    echo ""
    echo "❌ FAILED!"
    echo "Please check the error messages above."
    exit 1
fi
