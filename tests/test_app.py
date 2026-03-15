"""Smoke tests for app initialization."""


def test_app_creates(app):
    """App initializes without error."""
    assert app is not None


def test_app_has_blueprints(app):
    """All expected blueprints registered."""
    expected = {"auth", "shows", "playlists", "spotify", "api"}
    actual = set(app.blueprints.keys())
    assert expected <= actual, f"Missing blueprints: {expected - actual}"
