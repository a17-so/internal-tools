class SlideshowError(Exception):
    """Base error for slideshow maker."""


class ValidationError(SlideshowError):
    """Raised when format input or generated plans are invalid."""


class SourceError(SlideshowError):
    """Raised when asset sources fail."""
