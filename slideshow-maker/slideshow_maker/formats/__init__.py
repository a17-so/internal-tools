from slideshow_maker.formats.base import BaseFormat
from slideshow_maker.formats.skincare_v1 import SkincareFormatV1

_FORMATS: dict[str, type[BaseFormat]] = {
    SkincareFormatV1.format_id: SkincareFormatV1,
}


def get_format(format_id: str) -> BaseFormat:
    try:
        return _FORMATS[format_id]()
    except KeyError as exc:
        available = ", ".join(sorted(_FORMATS))
        raise ValueError(f"Unknown format '{format_id}'. Available: {available}") from exc


def list_formats() -> list[str]:
    return sorted(_FORMATS)
