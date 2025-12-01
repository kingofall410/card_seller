import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re, os
from pyzbar.pyzbar import decode

def preprocess_image(image_path):
    img = Image.open(image_path)
    img = img.convert("L")  # Convert to grayscale
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)  # Increase contrast
    return img

def preprocess_image(image_path):
    img = Image.open(image_path)
    img = img.convert("L")  # Convert to grayscale
    img = img.filter(ImageFilter.SHARPEN)
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2)  # Increase contrast
    return img

def extract_text_from_image(image_path):
    """
    Extracts text from an image file using Tesseract OCR.
    Keeps only the main block of text surrounded by newlines.
    """
    try:
        pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        img = preprocess_image(image_path)
        text = pytesseract.image_to_string(img, config="--psm 6").strip()
        return text
    except Exception as e:
        print(f"[Error] Could not process image {image_path}: {e}")
        return ""
    
def extract_psa_cert_from_barcode(image_path, region=None, angle=0):
    """
    Reads a barcode from an image and returns the PSA cert number.
    
    :param image_path: Path to the image file.
    :param region: Optional crop region (left, upper, right, lower).
    :param angle: Degrees to rotate the image (e.g., 90, 180, 270).
    :return: Cert number as a string, or None if not found.
    """
    try:
        img = Image.open(image_path)

        if region:
            img = img.crop(region)

        if angle:
            img = img.rotate(angle, expand=True)

        barcodes = decode(img)

        for barcode in barcodes:
            cert = barcode.data.decode("utf-8").strip()
            if cert.isdigit():
                return cert  # Return first numeric barcode found

        print("[Info] No numeric barcode found.")
        return None

    except Exception as e:
        print(f"[Error] Could not read barcode from image {image_path}: {e}")
        return None

def has_key_signals(text):
    return bool(re.search(r"#\d{1,3}", text) or re.search(r"\b\d{8,10}\b", text))
def has_hash_number(text):
    return bool(re.search(r"#\d{1,3}", text))

def has_cert_number(text):
    return bool(re.search(r"\b\d{8,10}\b", text))

def clean_ocr_text(text):
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Filter out lines with too many non-alphanumerics
        if sum(1 for c in line if not c.isalnum()) > len(line) * 0.5:
            continue
        # Filter out lines with no letters or digits
        if not any(c.isalnum() for c in line):
            continue
        cleaned.append(line)
    return cleaned

def extract_text_from_region(image_path, region=None, angles=None, autolabel=True):
    """
    Extracts text from a specific region of an image, trying all 4 orientations.
    Uses psm 3 first, then merges missing key fields from psm 6.
    """
    try:
        img = Image.open(image_path)

        if region:
            img = img.crop(region)
        elif autolabel:                    
            w, h = img.size
            left = int(w * 0.10)
            right = int(w * 0.90)
            top = 0
            bottom = int(h * 0.20)
            img = img.crop((left, top, right, bottom))

        # Preprocess base image
        img = img.convert("L")
        img = img.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2)

        pytesseract.pytesseract.tesseract_cmd = "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"

        # Run psm 3
        text_3 = pytesseract.image_to_string(img, config="--psm 3").strip()
        lines_3 = clean_ocr_text(text_3)
        text_3_joined = " ".join(lines_3)

         # Run psm 6 only if needed
        text_6 = pytesseract.image_to_string(img, config="--psm 6").strip()
        lines_6 = clean_ocr_text(text_6)
        text_6_joined = " ".join(lines_6)
        
        print(f"\nPSM 3 ✅]\n{lines_3}\n{'-'*40}")
        print(f"\nPSM 6 ✅]\n{lines_6}\n{'-'*40}")

        return lines_3

    except Exception as e:
        print(f"[Error] Could not process region in image {image_path}: {e}")
        return {}

if __name__ == "__main__":
    # Directory containing images
    image_dir = "C:\\Users\\Dan\\Desktop\\Test Input\\psa"
    # Define regions to test
    regions = {}

    # Loop through all image files in the directory
    for filename in os.listdir(image_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(image_dir, filename)
            print(f"\n=== {filename} ===")
            print("-" * 40)
            print(extract_text_from_region(image_path, autolabel=True))
            print("-" * 40)