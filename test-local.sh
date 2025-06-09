#!/bin/bash

# Local development testing script
# This script runs tests and code quality checks locally

echo "🧪 Running local tests and checks..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run code formatting
echo "🎨 Running code formatting..."
black --check . || (echo "❌ Code formatting issues found. Run 'black .' to fix." && exit 1)

# Run linting
echo "🔍 Running linting..."
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Run import sorting check
echo "📋 Checking import sorting..."
isort --check-only . || (echo "❌ Import sorting issues found. Run 'isort .' to fix." && exit 1)

# Run tests
echo "🧪 Running tests..."
pytest tests/ -v --tb=short

echo "✅ All checks passed!"
echo ""
echo "💡 Available commands:"
echo "  - Format code: black ."
echo "  - Sort imports: isort ."
echo "  - Run tests: pytest tests/ -v"
echo "  - Run with coverage: pytest tests/ --cov=. --cov-report=html"
