# Test configuration
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test environment variables
os.environ['TESTING'] = 'true'
os.environ['DISCORD_TOKEN'] = 'test_token_for_testing'

# Import required modules for testing
import pytest
import asyncio
import discord
from unittest.mock import MagicMock, AsyncMock

# Configure asyncio for pytest
pytest_plugins = ('pytest_asyncio',)


def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )


@pytest.fixture
def mock_discord_interaction():
    """Fixture for mocking Discord interaction"""
    interaction = AsyncMock()
    interaction.user.id = 123456789
    interaction.user.mention = "<@123456789>"
    interaction.user.display_name = "Test User"
    interaction.guild.id = 987654321
    interaction.response = AsyncMock()
    return interaction


@pytest.fixture
def mock_discord_guild():
    """Fixture for mocking Discord guild"""
    guild = MagicMock()
    guild.id = 987654321
    guild.get_channel = MagicMock()
    guild.get_role = MagicMock()
    guild.get_member = MagicMock()
    return guild


@pytest.fixture
def sample_config():
    """Fixture with sample configuration data"""
    return {
        "role_assignment_channel": 123456789,
        "audit_channel": 987654321,
        "military_roles": [111, 222, 333],
        "civilian_roles": [444, 555, 666],
        "moderators": {
            "users": [123456789],
            "roles": [777, 888]
        },
        "military_role_assignment_ping_roles": [999],
        "civilian_role_assignment_ping_roles": [101112]
    }
