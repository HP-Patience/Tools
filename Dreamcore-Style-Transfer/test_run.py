# -*- coding: utf-8 -*-
"""Test script for Dreamcore Style Transfer"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.image_processor import process_image, list_styles, ImageProcessor
from PIL import Image

# List all styles
styles = list_styles()
print(f"Available styles ({len(styles)}):")
for s in styles:
    print(f"  - {s['id']}: {s['name']}")

# Create test image
w, h = 400, 300
img = Image.new('RGB', (w, h))
pixels = img.load()
for x in range(w):
    for y in range(h):
        pixels[x, y] = (
            int(128 + 64 * (x / w - 0.5)),
            int(100 + 100 * (y / h - 0.5)),
            int(150 + 30 * ((x + y) / (w + h) - 0.5)),
        )
test_img = os.path.join(os.path.dirname(__file__), 'test_input.jpg')
img.save(test_img, quality=95)
print(f"\nTest image created: {test_img} ({w}x{h})")

# Create output dir
out_dir = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(out_dir, exist_ok=True)

# Test 3 styles x 3 intensities
test_cases = [
    ('dreamcore', 'standard'),
    ('backrooms', 'mild'),
    ('weirdcore', 'extreme'),
    ('chinese_dreamcore', 'standard'),
]
print("\nStyle processing tests:")
all_ok = True
for sid, intensity in test_cases:
    out_path = os.path.join(out_dir, f'test_{sid}_{intensity}.jpg')
    try:
        result = process_image(test_img, sid, intensity, out_path)
        size_kb = os.path.getsize(result) / 1024
        print(f"  OK {sid} ({intensity}): {size_kb:.1f} KB -> {result}")
    except Exception as e:
        print(f"  FAIL {sid} ({intensity}): {e}")
        all_ok = False

# Test all 10 styles
print("\nAll 10 styles test:")
for s in styles:
    out = os.path.join(out_dir, f'test_all_{s["id"]}.jpg')
    try:
        process_image(test_img, s['id'], 'standard', out)
        print(f"  OK {s['id']}")
    except Exception as e:
        print(f"  FAIL {s['id']}: {e}")
        all_ok = False

# Cleanup test input
os.remove(test_img)

if all_ok:
    print(f"\nAll tests passed! Output files in: {out_dir}")
else:
    print("\nSome tests failed!")
