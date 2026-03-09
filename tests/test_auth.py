"""
Auth flow tests.

Run with: uv run pytest tests/test_auth.py -v
"""

# =============================================================================
# EXPECTED REQUEST → RESPONSE PAIRS
# =============================================================================

# GET /auth/login — login page
LOGIN_PAGE_STATUS = 200
LOGIN_PAGE_CONTAINS = b"Email"

# GET / (no session) — redirect to login
HOME_NO_SESSION_STATUS = 302
HOME_NO_SESSION_REDIRECT = "/auth/login"

# POST /auth/login — submit email, show check email page
LOGIN_SUBMIT_STATUS = 200
LOGIN_SUBMIT_CONTAINS = b"Check your email"

# POST /auth/login (invalid email) — show error
LOGIN_INVALID_EMAIL_STATUS = 400
LOGIN_INVALID_EMAIL_CONTAINS = b"valid email"

# GET /auth/verify?token=valid — redirect to home
VERIFY_VALID_STATUS = 302
VERIFY_VALID_REDIRECT = "/"

# GET /auth/verify?token=invalid — error page
VERIFY_INVALID_STATUS = 400
VERIFY_INVALID_CONTAINS = b"Invalid"

# GET /auth/verify?token=expired — error page
VERIFY_EXPIRED_STATUS = 400
VERIFY_EXPIRED_CONTAINS = b"expired"

# GET /auth/verify?token=used — error page
VERIFY_USED_STATUS = 400
VERIFY_USED_CONTAINS = b"already been used"

# GET / (with session) — home page shows email
HOME_WITH_SESSION_STATUS = 200

# POST /auth/logout — redirect to login
LOGOUT_STATUS = 302
LOGOUT_REDIRECT = "/auth/login"


# =============================================================================
# TESTS
# =============================================================================


def test_login_page_loads(client):
    """GET /auth/login returns login form."""
    response = client.get("/auth/login")

    assert response.status_code == LOGIN_PAGE_STATUS
    assert LOGIN_PAGE_CONTAINS in response.data


def test_home_redirects_when_not_authed(client):
    """GET / redirects to login when no session."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == HOME_NO_SESSION_STATUS
    assert HOME_NO_SESSION_REDIRECT in response.headers.get("Location", "")


def test_submit_email_shows_check_email(client):
    """POST /auth/login with valid email shows check email page."""
    response = client.post("/auth/login", data={"email": "test@example.com"})

    assert response.status_code == LOGIN_SUBMIT_STATUS
    assert LOGIN_SUBMIT_CONTAINS in response.data


def test_submit_invalid_email_shows_error(client):
    """POST /auth/login with invalid email shows error."""
    response = client.post("/auth/login", data={"email": "not-an-email"})

    assert response.status_code == LOGIN_INVALID_EMAIL_STATUS
    assert LOGIN_INVALID_EMAIL_CONTAINS in response.data


def test_submit_email_creates_user(client, app):
    """POST /auth/login creates user if not exists."""
    from db_models import User

    client.post("/auth/login", data={"email": "newuser@example.com"})

    with app.app_context():
        user = User.query.filter_by(email="newuser@example.com").first()
        assert user is not None


def test_submit_email_creates_token(client, app):
    """POST /auth/login creates magic link token."""
    from db_models import User, MagicLinkToken

    client.post("/auth/login", data={"email": "tokentest@example.com"})

    with app.app_context():
        user = User.query.filter_by(email="tokentest@example.com").first()
        token = MagicLinkToken.query.filter_by(user_id=user.id).first()
        assert token is not None
        assert token.used_at is None


def test_verify_valid_token_redirects_to_home(client, create_user, create_token):
    """GET /auth/verify with valid token redirects to home."""
    user_id, _ = create_user("verify@example.com")
    token = create_token(user_id)

    response = client.get(f"/auth/verify?token={token}", follow_redirects=False)

    assert response.status_code == VERIFY_VALID_STATUS
    assert response.headers.get("Location") == VERIFY_VALID_REDIRECT


def test_verify_valid_token_creates_session(client, app, create_user, create_token):
    """GET /auth/verify with valid token creates session."""
    user_id, email = create_user("session@example.com")
    token = create_token(user_id)

    client.get(f"/auth/verify?token={token}")
    response = client.get("/", follow_redirects=True)

    assert response.status_code == HOME_WITH_SESSION_STATUS


def test_verify_invalid_token_shows_error(client):
    """GET /auth/verify with invalid token shows error."""
    response = client.get("/auth/verify?token=garbage-invalid-token")

    assert response.status_code == VERIFY_INVALID_STATUS
    assert VERIFY_INVALID_CONTAINS in response.data


def test_verify_expired_token_shows_error(client, create_user, create_token):
    """GET /auth/verify with expired token shows error."""
    user_id, _ = create_user("expired@example.com")
    token = create_token(user_id, expired=True)

    response = client.get(f"/auth/verify?token={token}")

    assert response.status_code == VERIFY_EXPIRED_STATUS
    assert VERIFY_EXPIRED_CONTAINS in response.data


def test_verify_used_token_shows_error(client, create_user, create_token):
    """GET /auth/verify with already-used token shows error."""
    user_id, _ = create_user("used@example.com")
    token = create_token(user_id, used=True)

    response = client.get(f"/auth/verify?token={token}")

    assert response.status_code == VERIFY_USED_STATUS
    assert VERIFY_USED_CONTAINS in response.data


def test_logout_redirects_to_login(client, create_user, create_token):
    """POST /auth/logout clears session and redirects."""
    user_id, _ = create_user("logout@example.com")
    token = create_token(user_id)

    # log in first
    client.get(f"/auth/verify?token={token}")

    # then log out
    response = client.post("/auth/logout", follow_redirects=False)

    assert response.status_code == LOGOUT_STATUS
    assert LOGOUT_REDIRECT in response.headers.get("Location", "")


def test_logout_clears_session(client, create_user, create_token):
    """After logout, home redirects to login again."""
    user_id, _ = create_user("cleartest@example.com")
    token = create_token(user_id)

    # log in
    client.get(f"/auth/verify?token={token}")

    # log out
    client.post("/auth/logout")

    # home should redirect now
    response = client.get("/", follow_redirects=False)

    assert response.status_code == HOME_NO_SESSION_STATUS
    assert HOME_NO_SESSION_REDIRECT in response.headers.get("Location", "")
