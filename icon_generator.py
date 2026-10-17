"""
Icon Generator for Realme Buds Controller
Generates application and dynamic system tray icons using Pillow.
"""

from PIL import Image, ImageDraw
import os

def create_app_icon(size: int = 128) -> Image.Image:
    """Generate high-res modern app icon."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    scale = size / 64.0

    # Draw rounded background squircle
    draw.rounded_rectangle(
        [2 * scale, 2 * scale, 62 * scale, 62 * scale],
        radius=14 * scale,
        fill=(24, 24, 28, 255),
        outline=(52, 52, 60, 255),
        width=int(1.5 * scale)
    )

    # Headband arc
    draw.arc(
        [15 * scale, 14 * scale, 49 * scale, 48 * scale],
        start=180,
        end=0,
        fill=(235, 235, 240, 255),
        width=int(4 * scale)
    )

    # Left ear cup (Realme yellow accent)
    draw.rounded_rectangle(
        [13 * scale, 28 * scale, 22 * scale, 48 * scale],
        radius=int(3 * scale),
        fill=(255, 196, 0, 255)
    )

    # Right ear cup (Realme yellow accent)
    draw.rounded_rectangle(
        [42 * scale, 28 * scale, 51 * scale, 48 * scale],
        radius=int(3 * scale),
        fill=(255, 196, 0, 255)
    )

    # Sound wave accents
    # Outer wave left
    draw.arc([6 * scale, 24 * scale, 14 * scale, 52 * scale], start=120, end=240, fill=(0, 160, 255, 180), width=int(2 * scale))
    # Outer wave right
    draw.arc([50 * scale, 24 * scale, 58 * scale, 52 * scale], start=-60, end=60, fill=(0, 160, 255, 180), width=int(2 * scale))

    return img

def create_tray_icon(mode: str = "1", state: str = "IDLE", size: int = 64) -> Image.Image:
    """
    Generate dynamic system tray icon.
    mode: '1' (ANC), '2' (Transparency), '3' (Normal)
    state: 'IDLE', 'BUSY', 'SUCCESS', 'ERROR'
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    scale = size / 64.0

    # Draw minimalist white headphone glyph
    # Headband
    draw.arc(
        [14 * scale, 12 * scale, 50 * scale, 48 * scale],
        start=180,
        end=0,
        fill=(255, 255, 255, 240),
        width=int(5 * scale)
    )

    # Ear cups
    draw.rounded_rectangle(
        [12 * scale, 27 * scale, 21 * scale, 47 * scale],
        radius=int(3.5 * scale),
        fill=(255, 255, 255, 240)
    )
    draw.rounded_rectangle(
        [43 * scale, 27 * scale, 52 * scale, 47 * scale],
        radius=int(3.5 * scale),
        fill=(255, 255, 255, 240)
    )

    # Determine badge color
    if state == "BUSY":
        badge_fill = (255, 204, 0)      # Yellow/Amber for busy
    elif state == "ERROR":
        badge_fill = (255, 59, 48)       # Red for error
    else:
        # Based on mode
        if mode == "1":
            badge_fill = (10, 132, 255)  # Win11/iOS Accent Blue (ANC)
        elif mode == "2":
            badge_fill = (255, 159, 10)  # Amber (Transparency)
        else:
            badge_fill = (142, 142, 147) # Slate / Gray (Normal Off)

    # Status / Mode Badge Dot in lower right corner
    draw.ellipse(
        [40 * scale, 40 * scale, 60 * scale, 60 * scale],
        fill=badge_fill,
        outline=(20, 20, 24, 255),
        width=int(2 * scale)
    )

    return img

def ensure_assets():
    """Generates and saves .ico and .png icons if not existing."""
    here = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(here, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    ico_path = os.path.join(assets_dir, "app_icon.ico")
    png_path = os.path.join(assets_dir, "app_icon.png")

    img = create_app_icon(256)
    img.save(png_path, format="PNG")

    # Multi-resolution ICO
    img_sizes = [create_app_icon(s) for s in [16, 24, 32, 48, 64, 128, 256]]
    img_sizes[0].save(ico_path, format="ICO", sizes=[(s, s) for s in [16, 24, 32, 48, 64, 128, 256]], append_images=img_sizes[1:])
    return ico_path, png_path

if __name__ == "__main__":
    ensure_assets()
    print("Assets generated successfully.")
