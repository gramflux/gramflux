"""Explicit, bounded interactive login; low-level methods remain single-attempt."""

import asyncio
import getpass
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import (
    AuthenticationError,
    ConfigurationError,
    LoginAttemptsExceeded,
    PasswordRequired,
)
from .raw import types

if TYPE_CHECKING:
    from .client import Client, LoginChallenge

Prompt = Callable[[str], Awaitable[str]]
Notify = Callable[[str], None]


async def _phone_input(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def _secret_input(prompt: str) -> str:
    return await asyncio.to_thread(getpass.getpass, prompt)


@dataclass(frozen=True, slots=True)
class LoginPrompts:
    """Replace prompts for async UIs/tests; notify receives value-free messages.

    EOF and cancellation propagate. Default terminal reads use a worker thread;
    cancelling an active OS terminal read cannot interrupt that thread. Supply
    cancellation-aware async callbacks for UIs requiring prompt cancellation.
    """

    phone: Prompt = _phone_input
    code: Prompt = _secret_input
    password: Prompt = _secret_input
    notify: Notify = print


async def _password_login(client: "Client", prompts: LoginPrompts, attempts: int) -> types.User:
    last_name = "PASSWORD_EMPTY"
    for attempt in range(1, attempts + 1):
        password = await prompts.password(f"Two-step password ({attempt}/{attempts}): ")
        try:
            if password:
                return await client.check_password(password)
        except AuthenticationError as error:
            if error.name != "PASSWORD_HASH_INVALID":
                raise
            last_name = error.name
        else:
            last_name = "PASSWORD_EMPTY"
        finally:
            del password
        if attempt < attempts:
            prompts.notify("Incorrect or empty password. Please try again.")
    raise LoginAttemptsExceeded("password", attempts, last_name)


async def _challenge(
    client: "Client",
    phone: str | None,
    prompts: LoginPrompts,
    attempts: int,
) -> tuple[str, "LoginChallenge"]:
    last_name = "PHONE_NUMBER_EMPTY"
    for attempt in range(1, attempts + 1):
        if phone is None:
            phone = await prompts.phone(f"Phone number ({attempt}/{attempts}): ")
        phone = phone.strip()
        try:
            if phone:
                return phone, await client.request_login_code(phone)
        except AuthenticationError as error:
            if error.name not in {"PHONE_NUMBER_INVALID", "PHONE_NUMBER_EMPTY"}:
                raise
            last_name = error.name
        else:
            last_name = "PHONE_NUMBER_EMPTY"
        if attempt < attempts:
            prompts.notify("Invalid or empty phone number. Please try again.")
        phone = None
    raise LoginAttemptsExceeded("phone", attempts, last_name)


async def login(
    client: "Client",
    *,
    phone: str | None,
    bot_token: str | None,
    max_attempts: int,
    prompts: LoginPrompts | None,
) -> types.User:
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ConfigurationError("max_attempts must be a positive integer")
    if phone is not None and bot_token is not None:
        raise ConfigurationError("choose phone or bot_token, not both")
    if phone is not None and not isinstance(phone, str):
        raise ConfigurationError("phone must be a string")
    if await client.is_authorized():
        return await client.get_me()
    if bot_token is not None:
        return await client.sign_in_bot(bot_token)

    ui = prompts or LoginPrompts()
    try:
        number, challenge = await _challenge(client, phone, ui, max_attempts)
    except PasswordRequired:
        # Telegram may issue a password challenge without sending a code.
        return await _password_login(client, ui, max_attempts)
    last_name = "PHONE_CODE_EMPTY"
    for attempt in range(1, max_attempts + 1):
        password_required = False
        code = await ui.code(f"Login code ({attempt}/{max_attempts}): ")
        try:
            if code.strip():
                return await client.sign_in(challenge, code.strip())
        except PasswordRequired:
            password_required = True
        except AuthenticationError as error:
            if error.name not in {"PHONE_CODE_INVALID", "PHONE_CODE_EMPTY", "PHONE_CODE_EXPIRED"}:
                raise
            last_name = error.name
        else:
            last_name = "PHONE_CODE_EMPTY"
        finally:
            del code
        if password_required:
            return await _password_login(client, ui, max_attempts)
        if attempt < max_attempts:
            if last_name == "PHONE_CODE_EXPIRED":
                ui.notify("Login code expired. Requesting a new code.")
                try:
                    challenge = await client.request_login_code(number)
                except PasswordRequired:
                    return await _password_login(client, ui, max_attempts)
            else:
                ui.notify("Incorrect or empty login code. Please try again.")
    raise LoginAttemptsExceeded("code", max_attempts, last_name)
