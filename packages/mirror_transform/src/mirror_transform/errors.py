"""Transform capability exceptions."""

from mirror_core.exceptions import MirrorError


class TransformError(MirrorError):
    """Raised when a transform step cannot construct the requested output."""
