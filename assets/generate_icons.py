"""Generate simple colored circle icons for system tray."""
from PIL import Image, ImageDraw

ICONS = {
    "icon_ready": "#4CAF50",        # green
    "icon_recording": "#f44336",     # red
    "icon_transcribing": "#FFC107",  # yellow
    "icon_ai": "#2196F3",           # blue
    "icon_loading": "#9E9E9E",      # grey
}

SIZE = 64

for name, color in ICONS.items():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse([margin, margin, SIZE - margin, SIZE - margin], fill=color)
    img.save(f"assets/{name}.png")
    print(f"Generated assets/{name}.png")
