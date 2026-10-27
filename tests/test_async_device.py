import asyncio
import html
import os
import re

import httpx2

from keycloak_auth.models.admin import user as u

from .test_async_admin import get_kc_client
from .test_async_openid import get_client

username = os.getenv("KEYCLOAK_USERNAME") or "test-user"
password = os.getenv("KEYCLOAK_PASSWORD") or "test-password"


def form_action(page: httpx2.Response, form_id: str | None = None) -> httpx2.URL:
    pattern = rf'<form[^>]*id="{form_id}"[^>]*>' if form_id else r"<form[^>]*>"
    form = re.search(pattern, page.text)
    assert form, f"form {form_id or ''} not found on {page.url.path}"
    action = re.search(r'action="([^"]+)"', form.group(0))
    assert action, "form has no action"
    # the consent form's action is relative
    return page.url.join(html.unescape(action.group(1)))


async def approve_device_login(verification_uri_complete: str) -> None:
    """Sign in as the test user and accept the consent screen, as the user would in a browser."""
    async with httpx2.AsyncClient(follow_redirects=True) as browser:
        page = await browser.get(verification_uri_complete)
        page = await browser.post(form_action(page, "kc-form-login"), data={"username": username, "password": password})

        # Keycloak asks for consent in the device flow, even when the client doesn't require it
        code = re.search(r'name="code"[^>]*value="([^"]*)"', page.text)
        assert code, f"consent screen not found on {page.url.path}"
        page = await browser.post(form_action(page), data={"code": html.unescape(code.group(1)), "accept": "Yes"})
        assert page.url.path.endswith("/device/status"), f"device login not approved, ended on {page.url.path}"


async def test_device_code_flow():
    async with get_client() as client, get_kc_client() as admin:
        users = await admin.get_users(u.QueryUser(username=username, exact=True))
        assert len(users) == 1
        user_id = users[0].id

        device = await client.device_code_grant()
        assert device.user_code in device.verification_uri_complete

        try:
            await approve_device_login(device.verification_uri_complete)
            async with asyncio.timeout(60):
                token = await client.device_code_to_token(device.device_code, device.interval)

            assert token.refresh_token
            try:
                decoded_token = await client.decode_token(token.access_token)
                assert decoded_token.azp == client.client_id
                assert decoded_token.preferred_username == username
            finally:
                # also ends the browser's login session
                await client.logout(token.refresh_token)
        finally:
            # accepting the consent screen stores a consent on the user
            consents = await admin.get_user_consents(user_id)
            if any(consent.clientId == client.client_id for consent in consents):
                await admin.revoke_user_consent(user_id, client.client_id)

        consents = await admin.get_user_consents(user_id)
        assert all(consent.clientId != client.client_id for consent in consents)
