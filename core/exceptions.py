"""Custom exceptions."""


class MoewieCopError(Exception):
    """Base exception for bot."""


class ValidationError(MoewieCopError):
    """Input validation error."""
