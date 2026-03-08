import resend
from flask import current_app


def send_magic_link(email: str, token: str) -> None:
    """Send magic link email via Resend."""
    base_url = current_app.config["BASE_URL"]
    login_url = f"{base_url}/auth/verify?token={token}"

    if current_app.config.get("DEV_MODE"):
        print(f"\n=== MAGIC LINK ===\n{login_url}\n==================\n")
        return

    resend.api_key = current_app.config["RESEND_API_KEY"]
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
