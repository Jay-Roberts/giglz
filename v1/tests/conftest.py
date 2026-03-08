"""Shared test fixtures."""

import pytest

from app import app

TEST_USER_ID = "test-host-user"


@pytest.fixture
def client():
    """Flask test client without auth."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def host_client():
    """Flask test client authenticated as host."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"] = TEST_USER_ID
            session["user_name"] = "Test Host"
        yield client
