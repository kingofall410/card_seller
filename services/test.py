import cv2
import numpy as np
import os
import argparse

def save_debug(img, step_number, step_name, variant, debug_dir):
    os.makedirs(debug_dir, exist_ok=True)
    filename = f"{step_number:02d}_{step_name}_{variant}.png"
    path = os.path.join(debug_dir, filename)
    cv2.imwrite(path, img)

def apply_sobel_edges(image, variant, debug_dir, threshold=40):
    grad_x = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
    magnitude = cv2.magnitude(grad_x, grad_y)
    edge_mask = cv2.convertScaleAbs(magnitude)
    save_debug(edge_mask, 2, "sobel_magnitude", variant, debug_dir)

    _, binary_mask = cv2.threshold(edge_mask, threshold, 255, cv2.THRESH_BINARY)
    save_debug(binary_mask, 3, "binary_edges", variant, debug_dir)

    return binary_mask

def draw_contours_and_card_mask(binary_mask, original_image, variant, debug_dir):
    if len(binary_mask.shape) == 3:
        binary_mask = cv2.cvtColor(binary_mask, cv2.COLOR_BGR2GRAY)

    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contour_img = original_image.copy()
    cv2.drawContours(contour_img, contours, -1, (255, 0, 0), 1)
    save_debug(contour_img, 4, "contours", variant, debug_dir)

    # Heuristic: high contour count + small average area → noisy background
    contour_count = len(contours)
    avg_area = np.mean([cv2.contourArea(c) for c in contours]) if contours else 0
    noisy = contour_count > 100 and avg_area < 500

    mask = np.zeros(binary_mask.shape, dtype=np.uint8)
    cv2.drawContours(mask, contours, -1, 255, -1)

    if noisy:
        card_mask = cv2.bitwise_not(mask)  # Invert: non-contoured = card fronts
    else:
        card_mask = mask  # Contours likely hug cards directly

    save_debug(card_mask, 5, "card_mask", variant, debug_dir)

def apply_preprocessing_variants(image, debug_dir, edge_threshold=40):
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    variants = {
        "originalimage": cv2.medianBlur(image, 5),
        "grayscale": cv2.medianBlur(gray, 5),
        "bilateral": cv2.medianBlur(cv2.bilateralFilter(gray, 9, 75, 75), 5),
    }

    # Radial brightness correction
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - center[0])**2 + (Y - center[1])**2)
    max_dist = np.max(dist)
    radial_mask = dist / max_dist
    radial_mask = cv2.GaussianBlur(radial_mask, (0, 0), sigmaX=0.5 * max_dist)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)
    v_boost = v_ch.astype(np.float32) + (radial_mask * 255 * 0.4)
    v_boost = np.clip(v_boost, 0, 255).astype(np.uint8)
    corrected_hsv = cv2.merge([h_ch, s_ch, v_boost])
    radial_corrected = cv2.cvtColor(corrected_hsv, cv2.COLOR_HSV2BGR)
    radial_gray = cv2.cvtColor(radial_corrected, cv2.COLOR_BGR2GRAY)

    variants["radial_corrected"] = cv2.medianBlur(radial_gray, 5)

    # 🔁 Save, detect edges, draw contours, and generate card mask
    for variant_name, variant_img in variants.items():
        save_debug(variant_img, 1, "preprocessed", variant_name, debug_dir)
        binary_mask = apply_sobel_edges(variant_img, variant_name, debug_dir, threshold=edge_threshold)
        draw_contours_and_card_mask(binary_mask, image, variant_name, debug_dir)

def main():
    parser = argparse.ArgumentParser(description="Detect card fronts using contour heuristics.")
    parser.add_argument("image_path", help="Path to input image")
    parser.add_argument("--debug_dir", default="debug_variants", help="Directory to save debug images")
    parser.add_argument("--edge_threshold", type=int, default=40, help="Threshold for binary edge mask")
    args = parser.parse_args()

    img = cv2.imread(args.image_path)
    if img is None:
        print(f"❌ Failed to read image: {args.image_path}")
        return

    print(f"✅ Processing image: {args.image_path}")
    apply_preprocessing_variants(img, debug_dir=args.debug_dir, edge_threshold=args.edge_threshold)
    print(f"✅ All debug images saved to: {args.debug_dir}")

if __name__ == "__main__":
    main()