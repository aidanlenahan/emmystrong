"""Shrink downloaded pictures before they're committed to the site.

Every image is resized to at most `max_width` pixels wide and saved as WebP at
moderate compression (quality 80), which is usually 70-90% smaller than the
original JPEG/PNG and looks the same on screen.

Needs Pillow (`pip install pillow`, done in the workflows). If Pillow isn't
installed or the image can't be read, the original bytes are kept as they are.
"""
import io

QUALITY = 80


def optimize(data, max_width, fallback_ext=".jpg"):
    """Return (bytes, extension) for an image file's raw bytes."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        print("::notice::Pillow isn't installed; keeping images as they are.")
        return data, fallback_ext
    try:
        im = Image.open(io.BytesIO(data))
        if getattr(im, "is_animated", False):
            return data, fallback_ext  # keep animated GIFs moving
        im = ImageOps.exif_transpose(im)  # phone photos: honor the rotation flag
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        im = im.convert("RGBA" if has_alpha else "RGB")
        if im.width > max_width:
            im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, "WEBP", quality=QUALITY, method=6)
        return out.getvalue(), ".webp"
    except Exception as e:
        print(f"::warning::Couldn't optimize an image ({type(e).__name__}); keeping the original.")
        return data, fallback_ext
