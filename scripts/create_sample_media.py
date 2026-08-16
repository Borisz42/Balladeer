from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

sample_dir = Path("sample_media")
sample_dir.mkdir(parents=True, exist_ok=True)

# 1. 9:16 Portrait Image
img_portrait = Image.new("RGB", (720, 1280), color=(30, 60, 100))
draw = ImageDraw.Draw(img_portrait)
draw.rectangle([100, 200, 620, 1080], fill=(20, 150, 180), outline=(255, 255, 255), width=6)
draw.text((220, 600), "Day 1: Kyoto Temple", fill=(255, 255, 255))
img_portrait.save(sample_dir / "portrait_day1.jpg")

# 2. 1:1 Square Image
img_square = Image.new("RGB", (1000, 1000), color=(100, 40, 60))
draw = ImageDraw.Draw(img_square)
draw.rectangle([150, 150, 850, 850], fill=(180, 50, 90), outline=(255, 255, 255), width=6)
draw.text((320, 500), "Day 2: Bamboo Grove", fill=(255, 255, 255))
img_square.save(sample_dir / "square_day2.jpg")

# 3. 16:9 Landscape Image
img_landscape = Image.new("RGB", (1920, 1080), color=(40, 90, 60))
draw = ImageDraw.Draw(img_landscape)
draw.rectangle([200, 150, 1720, 930], fill=(50, 160, 100), outline=(255, 255, 255), width=6)
draw.text((750, 500), "Day 3: Tokyo Neon", fill=(255, 255, 255))
img_landscape.save(sample_dir / "landscape_day3.jpg")

# Diary Text
diary_text = """Day 1: Arrived in Kyoto amidst gentle autumn rain. Walked through ancient temple grounds.
Day 2: Morning stroll through the whispering bamboo forest under golden sun.
Day 3: Shinkansen bullet train to Tokyo. Neon lights blazing across the city."""

(sample_dir / "diary.txt").write_text(diary_text, encoding="utf-8")
print("Sample media generated successfully in", sample_dir.resolve())
