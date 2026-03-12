from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from slideshow_maker.models import RenderTheme, RenderedSlides, SlidePlan


class Renderer:
    def __init__(self, theme: RenderTheme | None = None) -> None:
        self.theme = theme or RenderTheme()
        self._font_title = _load_font(self.theme.font_size_title)
        self._font_body = _load_font(self.theme.font_size_body)
        self._font_score = _load_font(self.theme.font_size_score)

    def render(self, slide_plan: SlidePlan, out_dir: Path) -> RenderedSlides:
        out_dir.mkdir(parents=True, exist_ok=True)
        slide_paths: list[Path] = []
        layout_debug: list[dict] = []

        for slide in slide_plan.slides:
            canvas = self._base_canvas(slide.image.path)
            draw = ImageDraw.Draw(canvas)

            if slide.top_text:
                top_rect = _draw_text_box(
                    draw,
                    text=slide.top_text,
                    font=self._font_body,
                    center_x=self.theme.width // 2,
                    y=90,
                    max_width=self.theme.width - 80,
                    theme=self.theme,
                )
            else:
                top_rect = None

            if slide.bottom_text:
                bottom_rect = _draw_text_box(
                    draw,
                    text=slide.bottom_text,
                    font=self._font_body,
                    center_x=self.theme.width // 2,
                    y=self.theme.height - 520,
                    max_width=self.theme.width - 80,
                    theme=self.theme,
                )
            else:
                bottom_rect = None

            score_rect = None
            if slide.score_text:
                score_rect = _draw_score_sticker(
                    draw,
                    text=slide.score_text,
                    font=self._font_score,
                    x=75,
                    y=360,
                    theme=self.theme,
                )

            overlay_rect = None
            if slide.cta and slide.scan_overlay and slide.scan_overlay.path.exists():
                overlay_rect = _paste_overlay(canvas, slide.scan_overlay.path)

            play_rect = _draw_play_icon(draw, self.theme.width // 2, self.theme.height // 2)

            slide_name = f"slide_{slide.index:02d}.png"
            slide_path = out_dir / slide_name
            canvas.save(slide_path)
            slide_paths.append(slide_path)

            layout_debug.append(
                {
                    "slide_index": slide.index,
                    "role": slide.role,
                    "top_rect": top_rect,
                    "bottom_rect": bottom_rect,
                    "score_rect": score_rect,
                    "scan_overlay_rect": overlay_rect,
                    "play_rect": play_rect,
                }
            )

        return RenderedSlides(slide_paths=slide_paths, debug={"layout": layout_debug})

    def _base_canvas(self, image_path: Path) -> Image.Image:
        if not image_path.exists():
            canvas = Image.new("RGB", (self.theme.width, self.theme.height), color="#DCDCDC")
            draw = ImageDraw.Draw(canvas)
            _draw_text_box(
                draw,
                text="unresolved asset",
                font=self._font_body,
                center_x=self.theme.width // 2,
                y=self.theme.height // 2,
                max_width=self.theme.width - 200,
                theme=self.theme,
            )
            return canvas

        image = Image.open(image_path).convert("RGB")
        return _fit_cover(image, self.theme.width, self.theme.height)


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = image.size
    scale = max(width / src_w, height / src_h)
    resized = image.resize((int(src_w * scale), int(src_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def _draw_text_box(draw: ImageDraw.ImageDraw, text: str, font, center_x: int, y: int, max_width: int, theme: RenderTheme):
    wrapped = _wrap_text(draw, text, font, max_width - (theme.box_padding * 2))
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    box_w = text_w + theme.box_padding * 2
    box_h = text_h + theme.box_padding * 2
    x0 = int(center_x - box_w / 2)
    y0 = y
    x1 = x0 + box_w
    y1 = y0 + box_h

    draw.rounded_rectangle((x0, y0, x1, y1), radius=theme.box_corner_radius, fill=theme.box_fill)
    draw.multiline_text(
        (x0 + theme.box_padding, y0 + theme.box_padding),
        wrapped,
        fill=theme.text_fill,
        font=font,
        spacing=8,
        align="center",
    )
    return {"x": x0, "y": y0, "w": box_w, "h": box_h}


def _draw_score_sticker(draw: ImageDraw.ImageDraw, text: str, font, x: int, y: int, theme: RenderTheme):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = (bbox[2] - bbox[0]) + 40
    h = (bbox[3] - bbox[1]) + 24
    x1 = x + w
    y1 = y + h
    draw.rounded_rectangle((x, y, x1, y1), radius=18, fill=theme.box_fill)
    draw.text((x + 20, y + 12), text, fill=theme.text_fill, font=font)
    return {"x": x, "y": y, "w": w, "h": h}


def _draw_play_icon(draw: ImageDraw.ImageDraw, center_x: int, center_y: int):
    radius = 80
    x0 = center_x - radius
    y0 = center_y - radius
    x1 = center_x + radius
    y1 = center_y + radius
    draw.ellipse((x0, y0, x1, y1), fill="#FFFFFF")
    triangle = [
        (center_x - 18, center_y - 30),
        (center_x - 18, center_y + 30),
        (center_x + 34, center_y),
    ]
    draw.polygon(triangle, fill="#E3E3E3")
    return {"x": x0, "y": y0, "w": radius * 2, "h": radius * 2}


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    words = text.split()
    if not words:
        return ""

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "\n".join(lines)


def _paste_overlay(canvas: Image.Image, overlay_path: Path):
    overlay = Image.open(overlay_path).convert("RGBA")
    max_w = int(canvas.width * 0.6)
    scale = min(max_w / overlay.width, 1.0)
    size = (int(overlay.width * scale), int(overlay.height * scale))
    overlay = overlay.resize(size, Image.Resampling.LANCZOS)
    x = (canvas.width - overlay.width) // 2
    y = int(canvas.height * 0.58)
    canvas.paste(overlay, (x, y), overlay)
    return {"x": x, "y": y, "w": overlay.width, "h": overlay.height}
