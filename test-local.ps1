# PowerShell script for local development testing
# This script runs tests and code quality checks locally

Write-Host "🧪 Running local tests and checks..." -ForegroundColor Cyan

# Check if virtual environment exists
if (!(Test-Path "venv")) {
    Write-Host "📦 Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "🔄 Activating virtual environment..." -ForegroundColor Yellow
& "venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "📦 Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run code formatting check
Write-Host "🎨 Running code formatting..." -ForegroundColor Yellow
$formatResult = & black --check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Code formatting issues found. Run 'black .' to fix." -ForegroundColor Red
    exit 1
}

# Run linting
Write-Host "🔍 Running linting..." -ForegroundColor Yellow
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

# Run import sorting check
Write-Host "📋 Checking import sorting..." -ForegroundColor Yellow
$isortResult = & isort --check-only .
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Import sorting issues found. Run 'isort .' to fix." -ForegroundColor Red
    exit 1
}

# Run tests
Write-Host "🧪 Running tests..." -ForegroundColor Yellow
pytest tests\ -v --tb=short

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ All checks passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 Available commands:" -ForegroundColor Cyan
    Write-Host "  - Format code: black ." -ForegroundColor White
    Write-Host "  - Sort imports: isort ." -ForegroundColor White
    Write-Host "  - Run tests: pytest tests\ -v" -ForegroundColor White
    Write-Host "  - Run with coverage: pytest tests\ --cov=. --cov-report=html" -ForegroundColor White
} else {
    Write-Host "❌ Some checks failed!" -ForegroundColor Red
    exit 1
}
