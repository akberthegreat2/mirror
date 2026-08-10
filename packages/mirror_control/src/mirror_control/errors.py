"""Errors raised by the framework-neutral control-plane service."""


class ControlError(Exception):
    """Base class for control-plane service errors."""


class UnknownEntityError(ControlError):
    """Raised when a control-plane entity name is not in the manifest."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"unknown control-plane entity {name!r}")


class NotFoundError(ControlError):
    """Raised when a control-plane entity does not exist."""


__all__ = ["ControlError", "NotFoundError", "UnknownEntityError"]
