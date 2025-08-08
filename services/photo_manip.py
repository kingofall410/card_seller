import os
import cv2
import numpy as np
#import ebay
import requests
from PIL import Image
from io import BytesIO
from sklearn.cluster import KMeans
#import pytesseract
#from pytesseract import Output



def is_valid_base64_image(encoded_str):
    try:
        decoded = base64.b64decode(encoded_str, validate=True)
        with Image.open(BytesIO(decoded)) as img:
            img.verify()  # Validate image structure
        return True
    except Exception as e:
        print(f"❌ Base64 does not decode into a valid image: {e}")
        return False



def get_average_hue_from_image(image):
    hsv_img = image.convert("HSV")
    pixels = list(hsv_img.getdata())
    hues = [pixel[0] for pixel in pixels]
    return sum(hues) / len(hues) if hues else float("inf")

def get_average_hue_from_url(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("RGB").resize((50, 50))
        return get_average_hue_from_image(img)
    except Exception as e:
        print(f"⚠️ Failed to process thumbnail: {e}")
        return float("inf")
    
def equalize_brightness_rgb(image_pil):
    """Equalizes brightness in HSV space and returns a normalized RGB image."""
    img = np.array(image_pil.convert("RGB"))
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    hsv[..., 2] = cv2.equalizeHist(hsv[..., 2])  # Equalize V (brightness)
    eq_rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    return Image.fromarray(eq_rgb)

def gray_world_white_balance_rgb(image_pil):
    """Applies gray-world white balance correction and returns a corrected RGB image."""
    img = np.array(image_pil.convert("RGB")).astype(np.float32)
    avg = img.mean(axis=(0, 1))
    gray_avg = avg.mean()
    scale = gray_avg / avg
    balanced = img * scale
    balanced = np.clip(balanced, 0, 255).astype(np.uint8)
    return Image.fromarray(balanced)

def get_dominant_hue_kmeans(image_pil, k=3):
    """Returns dominant hue value from the image using k-means clustering in HSV."""
    hsv = image_pil.convert("HSV").resize((50, 50))
    pixels = np.array(hsv).reshape(-1, 3)
    kmeans = KMeans(n_clusters=k, n_init='auto')
    kmeans.fit(pixels)
    dominant_hsv = kmeans.cluster_centers_[0]
    return dominant_hsv[0]  # Hue component

def detect_background_color_kmeans(image, clusters=3):
    """ Cluster edge pixels to estimate dominant background color. """
    h, w = image.shape[:2]
    border_thickness = 10
    border_pixels = np.concatenate([
        image[0:border_thickness, :, :].reshape(-1, 3),
        image[h-border_thickness:h, :, :].reshape(-1, 3),
        image[:, 0:border_thickness, :].reshape(-1, 3),
        image[:, w-border_thickness:w, :].reshape(-1, 3),
    ])

    kmeans = KMeans(n_clusters=clusters, n_init='auto')
    kmeans.fit(border_pixels)
    dominant = kmeans.cluster_centers_[0].astype(np.uint8)

    return dominant[::-1]  # RGB

def get_average_hue(image_url):
    try:
        response = requests.get(image_url, timeout=10)
        img = Image.open(BytesIO(response.content)).convert("RGB").resize((50, 50))
        hsv_img = img.convert("HSV")
        pixels = list(hsv_img.getdata())
        hues = [pixel[0] for pixel in pixels]
        return sum(hues) / len(hues)
    except Exception as e:
        print(f"⚠️ Failed to process image: {e}")
        return float("inf")  # Push failed images to the end
    
def validate_card_geometry(mask, expected_aspect=1.4, aspect_tolerance=0.3,
                           fill_threshold=0.95, max_area_fraction=0.85):
    """
    Validates whether the largest mask region resembles a proper card.
    """
    h, w = mask.shape[:2]
    image_area = w * h
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, None

    largest = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(largest)
    box_area = bw * bh
    contour_area = cv2.contourArea(largest)

    aspect_ratio = bw / bh if bh != 0 else 0
    fill_ratio = contour_area / box_area if box_area else 0

    aspect_match = abs(aspect_ratio - expected_aspect) <= expected_aspect * aspect_tolerance
    well_filled = fill_ratio >= fill_threshold
    not_full_frame = box_area < image_area * max_area_fraction

    if aspect_match and well_filled and not_full_frame:
        return True, (x, y, bw, bh)
    else:
        return False, None
    


def keep_largest_region(mask, output_path=None):
    """
    Retains and outlines the largest connected region in a binary mask.
    Ensures that the contour lies fully within the image bounds.
    Also saves a debug image showing all detected contours.
    """
    print("Foreground pixel count:", cv2.countNonZero(mask))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("⚠️ No contours found")
        return np.zeros_like(mask), None

    height, width = mask.shape[:2]
    max_area_ratio = 0.95
    valid_contours = [
        cnt for cnt in contours
        if cv2.contourArea(cnt) / (mask.shape[0] * mask.shape[1]) < max_area_ratio
    ]

    if not valid_contours:
        print("⚠️ All contours out of bounds")
        return np.zeros_like(mask), None

    # Use largest of the valid contours
    largest = max(valid_contours, key=cv2.contourArea)
    print(f"✅ Largest valid contour area: {cv2.contourArea(largest)}")

    # Fill and outline largest contour
    cleaned = np.zeros_like(mask)
    cv2.drawContours(cleaned, [largest], -1, 255, -1)
    cv2.drawContours(cleaned, [largest], -1, 128, 1)

    # Create debug visualization
    debug_contours = np.full((mask.shape[0], mask.shape[1], 3), 50, dtype=np.uint8)
    cv2.drawContours(debug_contours, valid_contours, -1, (0, 255, 255), 2)  # yellow for all valid
    cv2.drawContours(debug_contours, [largest], -1, (255, 0, 0), 2)         # blue for largest

    if output_path:
        save_debug_image(debug_contours, "x_debug_all_contours", output_path)

    return cleaned, largest

def highlight_reflections(image_hsv, threshold_v=230):
    """Create mask for overly bright reflection areas."""
    v_channel = image_hsv[:, :, 2]
    reflection_mask = cv2.inRange(v_channel, threshold_v, 255)
    return reflection_mask

def remove_background(image, bg_color_rgb, output_path):
    """
    Removes background using HSV masking, reflection suppression,
    and largest region isolation. Saves debug images at every step.
    """
    # 🔄 Convert to HSV
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    #save_debug_image(h, "debug_hue_channel", output_path)
    #save_debug_image(s, "debug_saturation_channel", output_path)
    #save_debug_image(v, "debug_value_channel", output_path)

    save_debug_image(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), "0_debug_hsv_conversion", output_path)

    # 🎨 Convert background color to HSV
    bg_color_hsv = cv2.cvtColor(np.uint8([[bg_color_rgb]]), cv2.COLOR_RGB2HSV)[0][0]
    swatch = np.full((50, 50, 3), bg_color_rgb[::-1], dtype=np.uint8)
    save_debug_image(swatch, "1_debug_bg_color_swatch", output_path)

    # 🎯 Adaptive HSV bounds
    hue_range = 10
    sat_range = min(255, bg_color_hsv[1] // 2 + 40)
    val_range = min(255, bg_color_hsv[2] // 2 + 40)


    lower_bound = np.maximum(bg_color_hsv - [hue_range, sat_range, val_range], [0, 0, 0]).astype(np.uint8)
    upper_bound = np.minimum(bg_color_hsv + [hue_range, sat_range, val_range], [179, 255, 255]).astype(np.uint8)

    print(f"🔧 HSV lower: {lower_bound}, upper: {upper_bound}")

    # 🖼️ Background mask
    bg_mask = cv2.inRange(hsv, lower_bound, upper_bound)
    save_debug_image(cv2.cvtColor(bg_mask, cv2.COLOR_GRAY2BGR), "2_debug_bg_mask", output_path)

    # ⚡ Reflection mask
    reflection_mask = highlight_reflections(hsv, 100)
    save_debug_image(cv2.cvtColor(reflection_mask, cv2.COLOR_GRAY2BGR), "3_debug_reflection_mask", output_path)

    # 🧃 Combined background mask
    #combined_mask = cv2.bitwise_or(bg_mask, reflection_mask)
    #save_debug_image(cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR), "4_debug_combined_mask_raw", output_path)

    #combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    #save_debug_image(cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR), "5_debug_combined_mask_closed", output_path)

    # 🧼 Foreground extraction
    foreground_mask = cv2.bitwise_not(bg_mask)
    save_debug_image(cv2.cvtColor(foreground_mask, cv2.COLOR_GRAY2BGR), "6_debug_foreground_mask_raw", output_path)

    cleaned_foreground = cv2.morphologyEx(foreground_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    save_debug_image(cv2.cvtColor(cleaned_foreground, cv2.COLOR_GRAY2BGR), "7_debug_foreground_cleaned", output_path)

    # 🧱 Largest region extraction
    largest_clean_region, largest_contour = keep_largest_region(cleaned_foreground, output_path)
    save_debug_image(cv2.cvtColor(largest_clean_region, cv2.COLOR_GRAY2BGR), "8_debug_largest_clean_region", output_path)

    # 🔲 Final mask from contour
    card_mask = np.zeros_like(foreground_mask)
    if largest_contour is not None:
        cv2.drawContours(card_mask, [largest_contour], -1, 255, -1)
    else:
        print("⚠️ No valid contour to draw")

    coverage = cv2.countNonZero(card_mask)
    print(f"🎯 Final card mask coverage: {coverage} / {card_mask.size} ({coverage / card_mask.size:.2%})")
    save_debug_image(cv2.cvtColor(card_mask, cv2.COLOR_GRAY2BGR), "9_debug_card_mask_final", output_path)

    # 🧪 Overlay visualization
    overlay = image.copy()
    overlay[card_mask > 0] = [255, 0, 0]  # blue highlight
    save_debug_image(cv2.addWeighted(image, 0.7, overlay, 0.3, 0), "10_debug_card_mask_overlay", output_path)

    # 🧩 Final isolated card area
    masked_card = cv2.bitwise_and(image, image, mask=card_mask)
    save_debug_image(masked_card, "11_debug_masked_card", output_path)

    return masked_card

def save_debug_image(image, stage_name, original_path):
    """
    Saves a debug image using the original filename and stage name, 
    placing it in the same folder as the final output.

    Parameters:
        image (np.array): The image to save.
        stage_name (str): Descriptive tag for the debug stage.
        original_path (str): Path to the original image file.
        output_path (str): Path to the final output file.
    """
    # Extract base filename from original file
    pass
    '''base_name = os.path.splitext(os.path.basename(original_path))[0]
    
    # Use final output directory
    output_dir = os.path.dirname(original_path)
    os.makedirs(output_dir, exist_ok=True)

    # Construct full debug image path
    debug_filename = f"{base_name}_{stage_name}.png"
    debug_path = os.path.join(output_dir, debug_filename)

    # Save the image
    cv2.imwrite(debug_path, image)'''

    
def isolate_card_from_mask(mask, aspect_range=(0.6, 2.0), fill_thresh=0.85, max_area_fraction=0.9):
    """
    Selects the largest well-filled contour that resembles a plausible rectangle.
    Filters out low-density, overly square or stretched shapes, glare-driven tails,
    and oversized blobs that span too much of the image.
    Returns a binary mask with the selected region filled in.
    """
    height, width = mask.shape[:2]
    image_area = width * height
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    max_area = 0

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        box_area = w * h
        contour_area = cv2.contourArea(cnt)
        aspect = w / h if h else 0
        fill_ratio = contour_area / box_area if box_area else 0

        # 💡 Only consider strong rectangular shapes
        is_rectangular = (aspect_range[0] <= aspect <= aspect_range[1])
        well_filled = (fill_ratio >= fill_thresh)
        within_size = (box_area < image_area * max_area_fraction)

        if is_rectangular and well_filled and within_size and box_area > max_area:
            best = cnt
            max_area = box_area

    filtered = np.zeros_like(mask)
    if best is not None:
        cv2.drawContours(filtered, [best], -1, 255, -1)
    return filtered


def score_contours_by_center_proximity(contours, image_shape, top_n=10):
    """
    Scores contours based on their centroid's proximity to image center.
    
    Returns top_n contours sorted by proximity.
    """
    H, W = image_shape[:2]
    center = np.array([W / 2, H / 2])
    scored_contours = []

    for cnt in contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            dist = np.linalg.norm(np.array([cx, cy]) - center)
            scored_contours.append((cnt, dist))

    # Sort contours by ascending distance (closest to center first)
    scored_contours.sort(key=lambda x: x[1])

    return [entry[0] for entry in scored_contours[:top_n]]

def find_card_like_contours(contours, image_shape, aspect_target=0.714, aspect_tolerance=0.15):
    H, W = image_shape[:2]
    image_area = H * W
    center = np.array([W / 2, H / 2])
    matched = []

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        bbox_area = w * h
        contour_area = cv2.contourArea(cnt)
        if bbox_area == 0 or contour_area == 0:
            continue

        aspect = w / h
        aspect_ok = abs(aspect - aspect_target) < aspect_tolerance
        area_ok = contour_area > 0.15 * image_area
        shape_ok = contour_area / bbox_area > 0.7

        # Check center alignment
        cx = x + w / 2
        cy = y + h / 2
        dist_to_center = np.linalg.norm(np.array([cx, cy]) - center)
        center_ok = dist_to_center < 0.3 * max(H, W)

        if aspect_ok and area_ok and shape_ok and center_ok:
            matched.append((cnt, dist_to_center))

    # Sort by proximity to center
    matched.sort(key=lambda x: x[1])
    return [m[0] for m in matched]

def merge_card_contour_group(contours, image_shape, center_n=5):
    H, W = image_shape[:2]
    center = np.array([W / 2, H / 2])
    
    # Score contours by proximity to center
    scored = []
    for cnt in contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]
            dist = np.linalg.norm(np.array([cx, cy]) - center)
            scored.append((cnt, dist))

    # Sort by center proximity
    scored.sort(key=lambda x: x[1])
    selected = [entry[0] for entry in scored[:center_n]]

    # Merge selected contours into a mask
    mask = np.zeros((H, W), dtype=np.uint8)
    cv2.drawContours(mask, selected, -1, 255, cv2.FILLED)

    # Morphological smoothing
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Get bounding box
    ys, xs = np.where(mask == 255)
    if len(xs) > 0 and len(ys) > 0:
        x1, x2 = np.min(xs), np.max(xs)
        y1, y2 = np.min(ys), np.max(ys)
        bbox = (x1, y1, x2 - x1, y2 - y1)
    else:
        bbox = None

    return mask, bbox

def visualize_all_contours(image, output_path=None, stage_name="debug_all_contours"):
    """
    Detects and draws all external contours on a neutral canvas.
    
    Parameters:
        image (np.array): Input image, either grayscale or color.
        output_path (str): Path for saving debug image (optional).
        stage_name (str): Label for saved image.
    Returns:
        canvas (np.array): BGR image with contours drawn.
    """
    # Ensure we’re working with a grayscale image for contour detection
    #gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    #_, bin_mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    edges = cv2.Canny(image, 100, 200)
    _, binary_edges = cv2.threshold(edges, 50, 255, cv2.THRESH_BINARY)
    
    #kernel = np.ones((3, 3), np.uint8)
    binary_edges = cv2.medianBlur(binary_edges, 5)

    contours, _ = cv2.findContours(binary_edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    merged_mask, bbox = merge_card_contour_group(contours, image.shape, int(len(contours)*.95))
    debug_mask = cv2.cvtColor(merged_mask, cv2.COLOR_GRAY2BGR)

    if bbox:
        x, y, w, h = bbox
        cv2.rectangle(debug_mask, (x, y), (x + w, y + h), (255, 0, 0), 2)
        print(f"📦 Bounding box: x={x}, y={y}, w={w}, h={h}")

    save_debug_image(debug_mask, "card_region_merged", output_path)
    #canvas = np.full((binary_edges.shape[0], binary_edges.shape[1], 3), 50, dtype=np.uint8)
    '''cv2.drawContours(canvas, contours, -1, (0, 255, 255), 2)
    save_debug_image(canvas, "all_edge_contours", output_path)

    merged_mask = np.zeros_like(gray)
    cv2.drawContours(merged_mask, contours, -1, 255, -1)

    top_centered_contours = score_contours_by_center_proximity(contours, image.shape, top_n=int(len(contours)*0.95))
    canvas = np.full((image.shape[0], image.shape[1], 3), 50, dtype=np.uint8)
    cv2.drawContours(canvas, top_centered_contours, -1, (0, 255, 255), 2)
    save_debug_image(canvas, "top_centered_contours", output_path)

    points = np.vstack(top_centered_contours)
    hull = cv2.convexHull(points)
    cv2.drawContours(merged_mask, [hull], -1, 255, -1)
    save_debug_image(cv2.cvtColor(merged_mask, cv2.COLOR_GRAY2BGR), "merged_edge_contours", output_path)'''


    # Find external contours
    #contours, _ = cv2.findContours(gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    print(f"🧠 Found {len(contours)} contours")

    # Create neutral canvas
    #canvas = np.full((gray.shape[0], gray.shape[1], 3), 50, dtype=np.uint8)

    # Draw all contours in yellow
    #cv2.drawContours(canvas, contours, -1, (0, 255, 255), 2)

    # Optionally save the debug image

def fit_card_from_mask(mask, expected_aspect=1.4, aspect_tolerance=0.2,
                       max_size_fraction=0.85, min_size_fraction=0.05):
    """
    Fits the minimum-area rectangle to the largest mask contour.
    Rejects stretched or full-frame rectangles.
    Returns valid crop box if geometry is trustworthy.
    """
    h, w = mask.shape[:2]
    image_area = h * w
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, None

    largest = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    box = np.intp(box)

    # Calculate box metrics
    box_w = int(np.linalg.norm(box[0] - box[1]))
    box_h = int(np.linalg.norm(box[1] - box[2]))
    box_area = box_w * box_h
    aspect = box_w / box_h if box_h else 0

    aspect_match = abs(aspect - expected_aspect) <= expected_aspect * aspect_tolerance
    size_ok = min_size_fraction * image_area <= box_area <= max_size_fraction * image_area

    if aspect_match and size_ok:
        x, y, w, h = cv2.boundingRect(box)
        return True, (x, y, w, h)
    else:
        return False, None



#this all does duplicate logic from below
def rotate_to_align_card(image, path):
    """
    Rotates the image so that the main card contour is aligned to vertical/horizontal axes.
    Uses minimum-area rectangle around the largest contour.
    Draws and saves the selected contour and bounding box.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blurred, 50, 200)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        print("⚠️ No contours found for alignment.")
        return image

    largest = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(largest)
    angle = rect[2]

    # 📏 Normalize angle
    if angle < -45:
        angle += 90
    elif angle > 45:
        angle -= 90

    # 🔒 Skip rotation if angle too steep
    if abs(angle) > 10:
        print(f"↩️ Detected angle {angle:.2f}° exceeds safe limit — skipping rotation.")
        return image

    print(f"🧭 Rotating image by {angle:.2f}° to align card geometry")

    # 🟩 Draw contour and bounding box
    debug = image.copy()
    box_points = cv2.boxPoints(rect)
    box_points = np.intp(box_points)
    cv2.drawContours(debug, [largest], -1, (0, 255, 0), 2)       # Green: raw contour
    cv2.drawContours(debug, [box_points], -1, (255, 255, 0), 2)  # Cyan: aligned bounding box
    save_debug_image(debug, "debug_alignment_contour", path)

    # 📐 Rotate image to align geometry
    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)

    cos = np.abs(rot_mat[0, 0])
    sin = np.abs(rot_mat[0, 1])
    new_w = int((height * sin) + (width * cos))
    new_h = int((height * cos) + (width * sin))

    # ✨ Portrait enforcement
    if new_w > new_h:
        new_w, new_h = new_h, new_w

    rot_mat[0, 2] += (new_w / 2) - center[0]
    rot_mat[1, 2] += (new_h / 2) - center[1]

    aligned = cv2.warpAffine(image, rot_mat, (new_w, new_h),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)

    return aligned
    

    
def validate_card_geometry_bb(mask, min_aspect=0.6, max_aspect=2.0,
                           min_area_fraction=0.05, max_area_fraction=0.95):
    h, w = mask.shape[:2]
    image_area = w * h
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return False, None

    largest = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(largest)
    box_area = bw * bh
    aspect_ratio = bw / bh if bh else 0

    size_ok = min_area_fraction * image_area <= box_area <= max_area_fraction * image_area
    aspect_ok = min_aspect <= aspect_ratio <= max_aspect

    if size_ok and aspect_ok:
        return True, (x, y, bw, bh)
    return False, None

def find_card_corners(image_path, debug=False):
    import cv2
    import numpy as np

    image = cv2.imread(image_path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 75, 200)

    # Find contours with hierarchy
    contours, hierarchy = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Merge small contours into a mask
    mask = np.zeros_like(gray)
    for cnt in contours:
        cv2.drawContours(mask, [cnt], -1, 255, -1)
    merged_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    card_contour = None
    for c in sorted(merged_contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(c) > 1000:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            if 4 <= len(approx) <= 6:  # Allow rough quads too
                card_contour = approx
                break

    if card_contour is None or len(card_contour) < 4:
        raise ValueError("No suitable card-like contour found.")

    def order_points(pts):
        pts = pts.reshape(-1, 2)
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        return np.array([
            pts[np.argmin(s)],
            pts[np.argmin(diff)],
            pts[np.argmax(s)],
            pts[np.argmax(diff)]
        ])

    corners = order_points(card_contour[:4])  # Just grab the 4 main corner points

    if debug:
        scale = 0.25
        small = cv2.resize(image.copy(), (0, 0), fx=scale, fy=scale)
        for idx, pt in enumerate(corners):
            pt_scaled = tuple((pt * scale).astype(int))
            cv2.circle(small, pt_scaled, 6, (0, 0, 255), -1)
            cv2.putText(small, str(idx), pt_scaled, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imshow("Corners Merged (25%)", small)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return corners
