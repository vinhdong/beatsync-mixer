# Test configuration
import pytest


def pytest_configure(config):
    """Configure pytest"""
    pytest.register_assert_rewrite('tests.test_app')
