import os
import cv2
import pytesseract
import re
from datetime import datetime

# ===============================
# Tesseract path
# ===============================
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ===============================
# Paths
# ===============================
BASE_DIR = os.path.dirname(__file__)
IMAGES_DIR = os.path.join(BASE_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)

# ===============================
# Save received image
# ===============================
def save_image(image_data):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(IMAGES_DIR, f"{timestamp}.jpg")

    with open(filename, "wb") as f:
        f.write(image_data)

    print("Image received:", filename)
    return filename

# ===============================
# OCR plate reader
# ===============================
def read_plate(image_path):
    img = cv2.imread(image_path)

    if img is None:
        print(f"Error: Could not read image from {image_path}")
        return ""

    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    versions = []

    _, v1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(v1)

    _, v2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    versions.append(v2)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(gray)
    _, v3 = cv2.threshold(cl, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(v3)

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    _, v4 = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(v4)

    configs = [
        '--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        '--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
        '--psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
    ]

    all_results = []

    for version in versions:
        for config in configs:
            text = pytesseract.image_to_string(version, config=config)
            text = re.sub(r'[^A-Z0-9]', '', text.upper()).strip()

            if text:
                match = re.search(r'[A-Z]{3}\d{3}', text)
                if match:
                    print(f"Plate found: {match.group()}")
                    return match.group()

                all_results.append(text)

    if not all_results:
        print(f"Warning: No plate detected in {image_path}")
        return ""

    best_result = max(all_results, key=len)
    print(f"Best result (no exact match): {best_result}")
    return best_result