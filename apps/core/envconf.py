"""Read required local secrets from the environment.

Seed commands and scripts call these helpers so passwords are never stored in
source. Values come from the process environment (typically a gitignored .env
file loaded by Django settings).
"""

import os

from django.core.management.base import CommandError


def required_env(name: str) -> str:
    """Return a non-empty environment variable or stop the command."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise CommandError(
            f"{name} is not set. Add it to your .env file (see .env.example)."
        )
    return value
