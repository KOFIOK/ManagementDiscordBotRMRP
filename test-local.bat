@echo off
REM Local development testing script for Windows
REM This script runs tests and code quality checks locally

echo 🧪 Running local tests and checks...

REM Check if virtual environment exists
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo 📦 Installing dependencies...
pip install -r requirements.txt
pip install -r requirements-dev.txt

REM Run code formatting check
echo 🎨 Running code formatting...
black --check .
if errorlevel 1 (
    echo ❌ Code formatting issues found. Run 'black .' to fix.
    exit /b 1
)

REM Run linting
echo 🔍 Running linting...
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

REM Run import sorting check
echo 📋 Checking import sorting...
isort --check-only .
if errorlevel 1 (
    echo ❌ Import sorting issues found. Run 'isort .' to fix.
    exit /b 1
)

REM Run tests
echo 🧪 Running tests...
pytest tests/ -v --tb=short

echo ✅ All checks passed!
echo.
echo 💡 Available commands:
echo   - Format code: black .
echo   - Sort imports: isort .
echo   - Run tests: pytest tests/ -v
echo   - Run with coverage: pytest tests/ --cov=. --cov-report=html

pause
