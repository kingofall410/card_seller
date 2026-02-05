import os
import re
import json
import datetime
import xml.etree.ElementTree as ET
from PIL import Image
from pyzbar.pyzbar import decode
from playwright.sync_api import sync_playwright
import cv2
import numpy as np
import pytesseract

# PSA API endpoints
CERT_LOOKUP_URL = "https://api.psacard.com/publicapi/cert/GetByCertNumber/"
IMAGE_LOOKUP_URL = "https://api.psacard.com/publicapi/cert/GetImagesByCertNumber/"

# Replace with your valid PSA access token
ACCESS_TOKEN = "waARmqUq2NdoBI6PRWTuOy9MTpAZ_-yA9yG1tZVdLdNCBajGehU-mVgLwZsAkzvSLNw6YB6kxaxhxGJGUV14JzOGAk1DA3misqShrZvx0YTKLyIIwDlJcFZNu_uNqanzrPPFTRNxCnmX-1qTUMl3QTy80dCovr7egQa_HMStHkFbKV1JwP4gd67FleBH3222QuMchWrx5PIqsjqepP2-z_FfFcpI6_LUuGXssasEFGz1cuwFj77Q4xqVFa2IDyHYsFEoZ3u_gSayZenHtmtE-6lwzpV-3__e8m6MKm1mz9e2nnUS"

# Shared headers for Playwright context
AUTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Authorization": f"Bearer {ACCESS_TOKEN}"
}
def extract_psa_label_cert_ocr_debug(image_path, region=None, angle=0, debug_dir="debug_ocr"):
    """
    Step-by-step OCR for PSA label with debug output AND saved images.
    """

    # Create debug directory
    os.makedirs(debug_dir, exist_ok=True)

    print(f"[1] Loading image: {image_path}")
    img = cv2.imread(image_path)
    if img is None:
        print("[1] ERROR: Could not load image.")
        return None
    print(f"[1] Image shape: {img.shape}")

    # Optional rotation
    if angle:
        print(f"[2] Rotating image by {angle} degrees")
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        pil_img = pil_img.rotate(angle, expand=True)
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    else:
        print("[2] No rotation applied")

    cv2.imwrite(f"{debug_dir}/step2_rotated.png", img)

    # Optional region crop
    '''if region:
        x1, y1, x2, y2 = region
        print(f"[3] Cropping region: ({x1}, {y1}) -> ({x2}, {y2})")
        img = img[y1:y2, x1:x2]
    else:
        print("[3] No region crop applied")
    
    cv2.imwrite(f"{debug_dir}/step3_cropped.png", img)'''

    # 4. Grayscale
    print("[4] Converting to grayscale")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(f"{debug_dir}/step4_gray.png", gray)

    # 5. Contrast boost
    print("[5] Boosting contrast (alpha=2.0)")
    gray_contrast = cv2.convertScaleAbs(gray, alpha=2.0, beta=0)
    cv2.imwrite(f"{debug_dir}/step5_contrast.png", gray_contrast)

    # 6. Adaptive threshold
    print("[6] Applying adaptive threshold")
    thresh = cv2.adaptiveThreshold(
        gray_contrast, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 10
    )
    cv2.imwrite(f"{debug_dir}/step6_thresh.png", thresh)

    # 7. Denoise
    print("[7] Applying median blur (ksize=3)")
    denoised = cv2.medianBlur(thresh, 3)
    cv2.imwrite(f"{debug_dir}/step7_denoised.png", denoised)

    # 8. Deskew
    print("[8] Deskewing based on text pixels")
    coords = np.column_stack(np.where(denoised > 0))
    if coords.size == 0:
        print("[8] No non-zero pixels found; skipping deskew")
        deskewed = denoised
    else:
        rect = cv2.minAreaRect(coords)
        angle_found = rect[-1]
        print(f"[8] Raw angle from minAreaRect: {angle_found}")

        if angle_found < -45:
            angle_corrected = -(90 + angle_found)
        else:
            angle_corrected = -angle_found

        print(f"[8] Corrected deskew angle: {angle_corrected}")

        (h, w) = denoised.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle_corrected, 1.0)
        deskewed = cv2.warpAffine(denoised, M, (w, h), flags=cv2.INTER_CUBIC)

    cv2.imwrite(f"{debug_dir}/step8_deskewed.png", deskewed)

    # 9. OCR
    print("[9] Running Tesseract OCR (digits only)")
    config = "--psm 6 -c tessedit_char_whitelist=0123456789"
    text = pytesseract.image_to_string(img, config=config)
    print(f"[9] Raw OCR text:\n{text!r}")

    # 10. Extract numeric cert
    print("[10] Parsing OCR output for numeric cert")
    for token in text.split():
        cleaned = "".join(c for c in token if c.isdigit())
        print(f"[10] Token: {token!r}, cleaned: {cleaned!r}")
        if cleaned.isdigit() and 6 <= len(cleaned) <= 10:
            print(f"[10] Found cert candidate: {cleaned}")
            return cleaned

    print("[10] No valid cert number found")
    return None

def extract_psa_label_cert(image_path, angle=0):
    """
    Detect the PSA label (red border), crop it, and extract the cert number via OCR.
    """

    # Load image (OpenCV uses BGR)
    img = cv2.imread(image_path)

    if img is None:
        return None

    # Rotate if needed
    if angle:
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        pil_img = pil_img.rotate(angle, expand=True)
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # Convert to HSV for color thresholding
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # PSA label red border is strong red; red wraps around hue=0
    lower_red1 = np.array([0, 80, 80])
    upper_red1 = np.array([10, 255, 255])

    lower_red2 = np.array([170, 80, 80])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = mask1 | mask2

    # Morphological cleanup
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Find contours of red regions
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Pick the largest red rectangle (PSA label)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    x, y, w, h = cv2.boundingRect(contours[0])

    # Crop the PSA label region
    label_region = img[y:y+h, x:x+w]

    # Convert to PIL for OCR
    pil_region = Image.fromarray(cv2.cvtColor(label_region, cv2.COLOR_BGR2RGB))

    # OCR the label
    text = pytesseract.image_to_string(pil_region)

    # Look for a cert number (PSA certs are numeric, usually 7–9 digits)
    for token in text.split():
        cleaned = "".join(c for c in token if c.isdigit())
        if cleaned.isdigit() and 6 <= len(cleaned) <= 10:
            return cleaned

    return None

def extract_psa_label_cert_multi(image_path, top_n=30, debug_dir="debug_candidates2"):
    """
    Detect red-bordered white rectangles that match PSA label geometry.
    """

    os.makedirs(debug_dir, exist_ok=True)

    img = cv2.imread(image_path)
    if img is None:
        print("ERROR: Could not load image")
        return None

    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Red mask
    lower_red1 = np.array([0, 80, 80])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([170, 80, 80])
    upper_red2 = np.array([180, 255, 255])

    red_mask = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)

    # Clean mask
    # --- Merge red border fragments into one contour ---
    kernel_big = np.ones((15, 15), np.uint8)

    # Dilate first to connect broken red edges
    red_mask = cv2.dilate(red_mask, kernel_big, iterations=2)

    # Then close to fill small gaps
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel_big)

    # Optional: slight erosion to restore border thickness
    red_mask = cv2.erode(red_mask, np.ones((5, 5), np.uint8), iterations=1)


    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("No red contours found")
        return None

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    candidates = contours[:top_n]

    print(f"Found {len(contours)} red regions, processing top {len(candidates)}")

    certs = []

    for idx, cnt in enumerate(candidates):
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h

        print(f"[Candidate {idx+1}] box=({x},{y},{w},{h}) area={area}")

        # --- 1. Reject tiny regions ---
        if w < 80 or h < 20:
            print(f"[Candidate {idx+1}] Too small, skipping")
            continue

        # --- 2. Aspect ratio check (PSA labels are wide) ---
        aspect = w / float(h)
        print(f"[Candidate {idx+1}] aspect ratio={aspect:.2f}")

        if aspect < 2.5 or aspect > 6.0:
            print(f"[Candidate {idx+1}] Aspect ratio not PSA-like, skipping")
            continue

        # Extract region
        region = img[y:y+h, x:x+w]

        # --- 3. White interior check ---
        inset = max(4, int(min(w, h) * 0.08))
        inner = region[inset:h-inset, inset:w-inset]

        if inner.size == 0:
            print(f"[Candidate {idx+1}] Inner region empty, skipping")
            continue

        inner_hsv = cv2.cvtColor(inner, cv2.COLOR_BGR2HSV)
        h_vals, s_vals, v_vals = cv2.split(inner_hsv)

        white_pixels = np.sum((s_vals < 60) & (v_vals > 150))
        total_pixels = inner.shape[0] * inner.shape[1]
        white_ratio = white_pixels / total_pixels

        print(f"[Candidate {idx+1}] white_ratio={white_ratio:.2f}")

        if white_ratio < 0.40:
            print(f"[Candidate {idx+1}] Not enough white interior, skipping")
            continue

        # --- 4. Save debug image ---
        debug_path = os.path.join(debug_dir, f"candidate_{idx+1}.png")
        cv2.imwrite(debug_path, region)
        print(f"[Candidate {idx+1}] Saved debug image → {debug_path}")

        # --- 5. OCR ---
        pil_region = Image.fromarray(cv2.cvtColor(region, cv2.COLOR_BGR2RGB))
        text = pytesseract.image_to_string(pil_region)
        print(f"[Candidate {idx+1}] OCR text: {text!r}")

        # Extract cert numbers
        for token in text.split():
            cleaned = "".join(c for c in token if c.isdigit())
            if cleaned.isdigit() and 6 <= len(cleaned) <= 10:
                print(f"[Candidate {idx+1}] Found cert: {cleaned}")
                certs.append(cleaned)

    return certs



def extract_psa_cert(image_path, region=None, angle=0):
    """Extract PSA cert number from barcode in image."""
    img = Image.open(image_path)
    if region:
        img = img.crop(region)
    if angle:
        img = img.rotate(angle, expand=True)

    barcodes = decode(img)
    for barcode in barcodes:
        cert = barcode.data.decode("utf-8").strip()
        if cert.isdigit():
            return cert
    return None

def parse_psa_cert_xml(xml_string, headers=None):
    """Parse PSA cert XML into structured fields."""
    try:
        if "API calls quota exceeded" in xml_string:
            retry_after = headers.get("retry-after") if headers else None
            return {
                "error": "API quota exceeded",
                "retry_after": retry_after,
                "raw_body": xml_string
            }

        cleaned = re.sub(r'^.*?<PublicCertificationModel', '<PublicCertificationModel', xml_string, flags=re.DOTALL)
        root = ET.fromstring(cleaned)
        ns = {'ns': 'http://schemas.datacontract.org/2004/07/PSA.Public.WebAPI.Models'}

        def find_text(tag):
            el = root.find(f".//ns:{tag}", ns)
            return el.text if el is not None else None

        return {
            "cert_number": find_text("CertNumber"),
            "grade": find_text("CardGrade"),
            "full_name": find_text("Subject"),
            "set_name": find_text("Brand"),
            "year": find_text("Year"),
            "card_number": find_text("CardNumber"),
            "category": find_text("Category"),
            "population_higher": find_text("PopulationHigher"),
            "total_population": find_text("TotalPopulation"),
            "spec_id": find_text("SpecID"),
            "spec_number": find_text("SpecNumber"),
        }

    except Exception as e:
        return {"error": f"Failed to parse XML: {e}", "raw_body": xml_string}

def parse_psa_images_xml(xml_string):
    """Parse PSA image XML into a list of dicts."""
    try:
        # Remove any leading text before the root element
        cleaned = re.sub(r'^.*?<ArrayOfPublicPSACertImage', '<ArrayOfPublicPSACertImage', xml_string, flags=re.DOTALL)

        root = ET.fromstring(cleaned)
        ns = {'ns': 'http://schemas.datacontract.org/2004/07/PSA.Public.WebAPI.Models'}

        images = []
        for img in root.findall("ns:PublicPSACertImage", ns):
            url_el = img.find("ns:ImageURL", ns)
            front_el = img.find("ns:IsFrontImage", ns)
            if front_el:
                images.append({"shareable_front_link":url_el})
            else:
                images.append({"shareable_reverse_link":url_el})
                
        return images
    except Exception as e:
        return {"error": f"Failed to parse image XML: {e}", "raw_body": xml_string}

def extract_psa_label_cert_ocr(image_path, region=None, angle=0):
    """
    Detect PSA label region (if region provided), preprocess it,
    and extract cert number using OCR.
    """

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        return None

    # Rotate if needed
    if angle:
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        pil_img = pil_img.rotate(angle, expand=True)
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    # Crop if region provided
    if region:
        x1, y1, x2, y2 = region
        img = img[y1:y2, x1:x2]

    # --- PREPROCESSING ---

    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Boost contrast
    gray = cv2.convertScaleAbs(gray, alpha=2.0, beta=0)

    # Adaptive threshold (handles glare)
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 10
    )

    # Remove noise
    denoised = cv2.medianBlur(thresh, 3)

    # Deskew using moments
    coords = np.column_stack(np.where(denoised > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    (h, w) = denoised.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    deskewed = cv2.warpAffine(denoised, M, (w, h), flags=cv2.INTER_CUBIC)

    # --- OCR ---

    # Numeric-only mode improves accuracy
    config = "--psm 6 -c tessedit_char_whitelist=0123456789"

    text = pytesseract.image_to_string(deskewed, config=config)

    # Extract numeric tokens
    for token in text.split():
        cleaned = "".join(c for c in token if c.isdigit())
        if cleaned.isdigit() and 6 <= len(cleaned) <= 10:
            return cleaned

    return None


def lookup_psa_cert_playwright(cert_number, context):
    """Use Playwright to bypass Cloudflare and fetch PSA cert info as XML."""
    url = f"{CERT_LOOKUP_URL}{cert_number}"
    print(url)
    page = context.new_page()
    try:
        response = page.goto(url, wait_until="networkidle")
        xml_body = page.inner_text("body")
        headers = dict(response.headers) if response else {}
        parsed_data = parse_psa_cert_xml(xml_body, headers=headers)
        return parsed_data
    except Exception as e:
        return {"error": f"Cert lookup failed: {e}"}
    finally:
        page.close()

def fetch_psa_images_playwright(cert_number, context):
    """Fetch PSA slab images using Playwright to bypass Cloudflare."""
    url = f"https://api.psacard.com/publicapi/cert/GetImagesByCertNumber/{cert_number}"
    print(url)
    page = context.new_page()
    try:
        response = page.goto(url, wait_until="networkidle")
        xml_body = page.inner_text("body")
        return parse_psa_images_xml(xml_body)
    except Exception as e:
        return {"error": f"Image lookup failed: {e}"}
    finally:
        page.close()


def scan_and_lookup(image_path, region=(0,0,480, 100), angle=0):
    region=(0,0,480, 100)
    angle=0
    """Full pipeline: scan image, extract cert, lookup card info + images."""
    print("icup", image_path)
    #cert = extract_psa_cert(image_path, region, angle)
    #cert = extract_psa_label_cert(image_path, angle)
    cert = extract_psa_label_cert_multi(image_path)     
    #cert = extract_psa_label_cert_ocr(image_path, region, angle)
    #cert = extract_psa_label_cert_ocr_debug(image_path, region, angle)
    print(cert)
    if not cert:
        return {"error": "No valid barcode found."}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(extra_http_headers=AUTH_HEADERS)

        card_info = lookup_psa_cert_playwright(cert, context)
        if "cert_number" in card_info:
            card_info["images"] = fetch_psa_images_playwright(card_info["cert_number"], context)

        browser.close()
        return card_info

if __name__ == "__main__":
    image_dir = "C:\\Users\\Dan\\Desktop\\Test Input\\psa"
    for filename in os.listdir(image_dir):
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            image_path = os.path.join(image_dir, filename)
            print(f"\n=== {filename} ===")
            print("-" * 40)
            result = scan_and_lookup(image_path, angle=270)
            print(result)
            print("-" * 40)
