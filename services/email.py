import resend


def _get_settings():
    from flask import current_app
    return current_app.extensions["settings"]


def send_magic_link(email: str, token: str) -> None:
    """Send magic link email via Resend."""
    settings = _get_settings()
    login_url = f"{settings.base_url}/auth/verify?token={token}"

    if settings.dev_mode:
        print(f"\n=== MAGIC LINK ===\n{login_url}\n==================\n")
        return

    resend.api_key = settings.resend_api_key
    resend.Emails.send(
        {
            "from": "Giglz <login@giglz.app>",  # update domain after verification
            "to": email,
            "subject": "Your Giglz login link",
            "html": f"""
            <p>Click to log in to Giglz:</p>
            <p><a href="{login_url}">Log in</a></p>
            <p>This link expires in 15 minutes.</p>
            <p>If you didn't request this, ignore this email.</p>
        """,
        }
    )
