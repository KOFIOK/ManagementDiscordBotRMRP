# Tests for Army Discord Bot

This directory contains automated tests for the Discord bot functionality.

## Test Structure

- `test_role_assignment.py` - Tests for role assignment forms and validation
- `test_utils.py` - Tests for utility functions and configuration management
- `test_integration.py` - Integration tests for bot functionality
- `conftest.py` - Test configuration and fixtures

## Running Tests

### Run all tests:
```bash
pytest tests/ -v
```

### Run specific test file:
```bash
pytest tests/test_role_assignment.py -v
```

### Run with coverage:
```bash
pytest tests/ --cov=. --cov-report=html
```

### Run only unit tests:
```bash
pytest tests/ -m unit -v
```

### Run only integration tests:
```bash
pytest tests/ -m integration -v
```

## Test Categories

- **Unit Tests**: Test individual functions and methods
- **Integration Tests**: Test component interaction and full workflows
- **Validation Tests**: Test data validation and error handling

## Mock Data

Tests use mocked Discord objects to avoid requiring real Discord connections.
All sensitive data should be mocked or use test environment variables.

## Coverage

Aim for >80% code coverage on critical components:
- Form validation logic
- Configuration management
- Role assignment workflows
- Error handling paths
