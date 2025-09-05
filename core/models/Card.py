import os
from django.db import models
from core.models.Cropping import CropParams, CroppedImage
import numpy as np
import cv2
from django.core.files.base import ContentFile
from core.models.CardSearchResult import CardSearchResult
'''think about next steps: many require more ebay api work
0.test expanding search results
1. locking specific fields to improve search results
    a. by setting attribute filters --> don't seem to work
    b. by filtering based on title tokens
2. text search
3. pricing
    a. ebay listing prices --> pulled regularly and stored for analytics
    b market movers scrape, 120pt
long term: market movers, 
4. listing
5. Long term selling analytics
6. google trends'''
class Collection(models.Model):
    create_date = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=100, blank=True)
    parent_collection = models.ForeignKey('self', on_delete=models.CASCADE, related_name="subcollections", null=True)
           
    @classmethod
    def get_default(cls):
        return Collection.objects.first()

    def get_default_exports(self):
        return (card.active_search_results() for card in self.cards.all())
    
    def get_size(self):
        return len(self.cards.all())


class Card(models.Model):
    upload_date = models.DateTimeField(auto_now_add=True)
    
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="cards")

    reverse_id = models.CharField(max_length=100, blank=True)
    uploaded_image = models.OneToOneField(CroppedImage,  on_delete=models.CASCADE, related_name="card_as_upload", null=True)
    portrait_image = models.OneToOneField(CroppedImage,  on_delete=models.CASCADE, related_name="card_as_cropped", null=True)
    cropped_image = models.OneToOneField(CroppedImage,  on_delete=models.CASCADE, related_name="card_as_portrait", null=True)

    reverse_image = models.OneToOneField(CroppedImage,  on_delete=models.CASCADE, related_name="card_as_reverse", null=True)
    cropped_reverse = models.OneToOneField(CroppedImage,  on_delete=models.CASCADE, related_name="card_as_reverse_crop", null=True)
    portrait_reverse = models.OneToOneField(CroppedImage,  on_delete=models.CASCADE, related_name="card_as_reverse_portrait", null=True)
   

    def get_lookup_image(self):
        if self.cropped_image:
            return self.cropped_image.img
        else:
            return self.uploaded_image.img
        
    def get_search_strings(self):
        return self.active_search_results().get_search_strings()
        
    def active_search_results(self):
        return self.search_results.last()

    @property
    def search_count(self):
        return len(self.search_results.all())
    
    @classmethod
    def find_back_by_alpha(cls, front_filepath):
        print("front_filepath: ", front_filepath)
        directory = os.path.dirname(front_filepath)
        file_list = sorted(f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f)))
        print("file_list: ", file_list)
        # Find current index
        current_name = os.path.basename(front_filepath)
        print("current_name: ", current_name)
        try:
            current_index = file_list.index(current_name)
            print("current_index: ", current_index)
            next_index = current_index + 1
            print("next_index: ", next_index)
            return os.path.join(directory, file_list[next_index])
        except (ValueError, IndexError):
            return None

    def crop_display_img(self):
        if self.cropped_image:
            return self.cropped_image.img.url
        return self.portrait_image.img.url
    
    def reverse_crop_display_img(self):
        if self.cropped_reverse:
            return self.cropped_reverse
        return self.reverse_image

    @classmethod
    def from_filename(cls, collection, filepath, crop=True, match_back=True):
        """
        Create and save a Card instance from a file path.
        """
        match_back_success = False
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Image not found: {filepath}")
        
        #clean all this up, throw out the paths and just keep files
        #create card object and save front/back images
        card = cls()
        card.collection = collection
        card.save()

        card.uploaded_image = CroppedImage.create(save_to_filepath=filepath)
        back_filepath = None
        if match_back:
            back_filepath = card.find_back_by_alpha(filepath)
            if back_filepath:
                
                # Save cropped image and path
                base, _ = os.path.splitext(os.path.basename(filepath))
                card.reverse_image = CroppedImage.create(save_to_filepath=os.path.join("cropped_cards/", back_filepath))
                match_back_success = True
                card.reverse_id = str(card.id)+"R"
                
        # Handle cropping if requested
        if crop:

            cropped, portrait, crop_params = card.crop_and_align_card(filepath)            
            if cropped and portrait and crop_params:
                # Save cropped image and path
                base, _ = os.path.splitext(os.path.basename(filepath))
                cropped_filename = f"{base}_cropped.jpg"    
                print(cropped_filename)
                card.cropped_image = CroppedImage.create(save_to_filepath=cropped_filename, content=cropped, crop_params=crop_params)

                # Save portrait image and path
                portrait_filename = f"{base}_portrait.jpg"    
                card.portrait_image = CroppedImage.create(save_to_filepath=portrait_filename, content=portrait)
                
                card.save()
                
                if match_back and card.reverse_image:   
                    
                    # Crop and save reverse 
                    cropped_back, portrait_back, crop_params_back = card.crop_and_align_card(card.reverse_image.img.path)
                    if cropped_back and portrait_back and crop_params_back:
                        base, _ = os.path.splitext(os.path.basename(card.reverse_image.img.path))
                        cropped_back_filename = f"{base}_cropped.jpg"    
                        portrait_back_filename = f"{base}_portrait.jpg"
                        print(cropped_back_filename)
                        print(portrait_back_filename)
                        card.cropped_reverse = CroppedImage.create(save_to_filepath=cropped_back_filename, content=cropped_back, crop_params=crop_params_back)
                        card.save()
                        print(card.cropped_reverse.crop_params.first())
                        print("port-1: ", card.cropped_reverse.img.url)
                        # Save portrait back image and path
                        card.portrait_reverse = CroppedImage.create(save_to_filepath=portrait_back_filename, content=portrait_back)
                        card.save()
        '''print("IDs: ", card.id, card.reverse_id)
        print("crop: ", card.cropped_image.url())
        print("rev port:", card.portrait_reverse.url() if card.portrait_reverse else "None")
        print("rev crop:", card.cropped_reverse.url() if card.cropped_reverse else "None")
        print("img: ", card.uploaded_image.url() if card.uploaded_image else "None")
        print("rev:", card.reverse_image.url() if card.reverse_image else "None")'''

        return card, match_back_success
    
    def __lt__(self, other):
        return self.id < other.id

    def __eq__(self, other):
        return self.id == other.id
    
    def __hash__(self):
        return hash(self.id)

    
    def compute_highlight_threshold_v(self, hsv_image, percentile=50):
        """
        Determines adaptive threshold_v for glare based on V channel distribution.
        percentile=98 captures top 2% brightest pixels.
        """
        v_channel = hsv_image[:, :, 2].flatten()
        threshold = np.percentile(v_channel, percentile)
        threshold = min(255, max(100, int(threshold)))  # Clamp within reasonable range
        print(f"🔎 Adaptive threshold_v set to: {threshold}")
        return threshold

    def detect_background_color(self, image, sample_size=50):
        """
        Samples the top-left, top-right, bottom-left, and bottom-right corners
        and returns the median RGB background color across all four.
        """
        h, w = image.shape[:2]
        s = sample_size

        corners = [
            image[0:s, 0:s],                 # top-left
            image[0:s, w-s:w],               # top-right
            image[h-s:h, 0:s],               # bottom-left
            image[h-s:h, w-s:w]              # bottom-right
        ]

        all_pixels = np.vstack([corner.reshape(-1, 3) for corner in corners])
        median_bgr = np.median(all_pixels, axis=0).astype(np.uint8)

        return median_bgr[::-1]  # Convert BGR to RGB

    def highlight_reflections(self, image_hsv, threshold_v=230):
        """Create mask for overly bright reflection areas."""
        v_channel = image_hsv[:, :, 2]
        reflection_mask = cv2.inRange(v_channel, threshold_v, 255)
        return reflection_mask

    def keep_largest_region(self, mask):
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

        return cleaned, largest

    def remove_background(self, image, bg_color_rgb):
        """
        Removes background using HSV masking, reflection suppression,
        and largest region isolation. Saves debug images at every step.
        """
        # 🔄 Convert to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # 🎨 Convert background color to HSV
        bg_color_hsv = cv2.cvtColor(np.uint8([[bg_color_rgb]]), cv2.COLOR_RGB2HSV)[0][0]
        swatch = np.full((50, 50, 3), bg_color_rgb[::-1], dtype=np.uint8)

        # 🎯 Adaptive HSV bounds
        hue_range = 10
        sat_range = min(255, bg_color_hsv[1] // 2 + 40)
        val_range = min(255, bg_color_hsv[2] // 2 + 40)


        lower_bound = np.maximum(bg_color_hsv - [hue_range, sat_range, val_range], [0, 0, 0]).astype(np.uint8)
        upper_bound = np.minimum(bg_color_hsv + [hue_range, sat_range, val_range], [179, 255, 255]).astype(np.uint8)

        print(f"🔧 HSV lower: {lower_bound}, upper: {upper_bound}")

        # 🖼️ Background mask
        bg_mask = cv2.inRange(hsv, lower_bound, upper_bound)
        #save_debug_image(cv2.cvtColor(bg_mask, cv2.COLOR_GRAY2BGR), "2_debug_bg_mask", output_path)

        # ⚡ Reflection mask
        #reflection_mask = self.highlight_reflections(hsv, 100)
        #save_debug_image(cv2.cvtColor(reflection_mask, cv2.COLOR_GRAY2BGR), "3_debug_reflection_mask", output_path)

        # 🧃 Combined background mask
        #combined_mask = cv2.bitwise_or(bg_mask, reflection_mask)
        #save_debug_image(cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR), "4_debug_combined_mask_raw", output_path)

        #combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        #save_debug_image(cv2.cvtColor(combined_mask, cv2.COLOR_GRAY2BGR), "5_debug_combined_mask_closed", output_path)

        # 🧼 Foreground extraction
        foreground_mask = cv2.bitwise_not(bg_mask)
        #save_debug_image(cv2.cvtColor(foreground_mask, cv2.COLOR_GRAY2BGR), "6_debug_foreground_mask_raw", output_path)

        cleaned_foreground = cv2.morphologyEx(foreground_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        #save_debug_image(cv2.cvtColor(cleaned_foreground, cv2.COLOR_GRAY2BGR), "7_debug_foreground_cleaned", output_path)

        # 🧱 Largest region extraction
        largest_clean_region, largest_contour = self.keep_largest_region(cleaned_foreground)
        #save_debug_image(cv2.cvtColor(largest_clean_region, cv2.COLOR_GRAY2BGR), "8_debug_largest_clean_region", output_path)

        # 🔲 Final mask from contour
        card_mask = np.zeros_like(foreground_mask)
        if largest_contour is not None:
            cv2.drawContours(card_mask, [largest_contour], -1, 255, -1)
        else:
            print("⚠️ No valid contour to draw")

        coverage = cv2.countNonZero(card_mask)
        print(f"🎯 Final card mask coverage: {coverage} / {card_mask.size} ({coverage / card_mask.size:.2%})")
        #save_debug_image(cv2.cvtColor(card_mask, cv2.COLOR_GRAY2BGR), "9_debug_card_mask_final", output_path)

        # 🧪 Overlay visualization
        overlay = image.copy()
        overlay[card_mask > 0] = [255, 0, 0]  # blue highlight
        #save_debug_image(cv2.addWeighted(image, 0.7, overlay, 0.3, 0), "10_debug_card_mask_overlay", output_path)

        # 🧩 Final isolated card area
        masked_card = cv2.bitwise_and(image, image, mask=card_mask)
        #save_debug_image(masked_card, "11_debug_masked_card", output_path)

        return masked_card

    def crop_and_align_card(self, filepath, buffer=15, max_rotation=5, create_portrait=True):
        print("Processing image for cropping and alignment:", filepath)
        #read image into mem
        img = cv2.imread(filepath)
        if img is None:
            print("⚠️ Failed to read image.")
            return None, None, None    

        original_image_height, original_image_width = img.shape[:2]
        #print("img", img)

        # Detect background color, minimizing impact of reflections, and remove BG
        bg_color_rgb = self.detect_background_color(img)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        threshold_v = self.compute_highlight_threshold_v(hsv)
        
        reflection_mask = self.highlight_reflections(hsv, threshold_v)
        #save_debug_image(reflection_mask, "reflection_mask", output_path)

        highlight_suppressed = cv2.bitwise_and(img, img, mask=cv2.bitwise_not(reflection_mask))
        no_bg_image = self.remove_background(highlight_suppressed, bg_color_rgb)

        # Build an overcomplicated 🎯 Gradient-based edge map
        gray = cv2.cvtColor(no_bg_image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        kernel = np.ones((3, 3), np.uint8)
        opened = cv2.morphologyEx(blurred, cv2.MORPH_OPEN, kernel)

        grad_x = cv2.Sobel(opened, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(opened, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        edge_mask = cv2.convertScaleAbs(magnitude)
        _, edge_mask = cv2.threshold(edge_mask, 40, 255, cv2.THRESH_BINARY)

        # 🧼 Suppress highlight areas from edge mask
        edge_mask = cv2.bitwise_and(edge_mask, cv2.bitwise_not(reflection_mask))

        # 🔧 Morphological cleanup
        edge_mask = cv2.morphologyEx(edge_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
        edge_mask = cv2.dilate(edge_mask, np.ones((5, 5), np.uint8), iterations=1)
        #save_debug_image(cv2.cvtColor(edge_mask, cv2.COLOR_GRAY2BGR), "debug_gradient_edges", output_path)

        # Find all contours visible in the image
        contours, _ = cv2.findContours(edge_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        selected_contour = None
        max_box_area = 0

        #save the biggest one with a reasonable aspect ratio and coverage %
        for contour in contours:
            rect = cv2.minAreaRect(contour)
            (w, h) = rect[1]
            box_area = w * h
            aspect = max(w, h) / min(w, h) if min(w, h) else 0

            if (0.5 < aspect < 2.2 and
                original_image_width * original_image_height * 0.15 < box_area < original_image_width * original_image_height * 0.98 and
                box_area > max_box_area):
                selected_contour = contour
                max_box_area = box_area

        # 🔁 Fallback to largest contour if nothing passes
        if selected_contour is None:
            if len(contours) > 0:
                print("⚠️ No suitable contour met criteria — falling back to largest.")
                selected_contour = max(contours, key=cv2.contourArea)
            else:
                print("⚠️ No contours found — falling back to boundary.")
                selected_contour = np.array([
                    [[0, 0]],
                    [[original_image_width - 1, 0]],
                    [[original_image_width - 1, original_image_height - 1]],
                    [[0, original_image_height - 1]]
            ])
        
        rect = cv2.minAreaRect(selected_contour)
        bounding_box_points = cv2.boxPoints(rect)
        bounding_box_points = bounding_box_points.astype(np.intp)

        # Normalize OpenCV angle and clamp rotation
        bounding_box_rotation = rect[2]

        if bounding_box_rotation > 45:
            bounding_box_rotation -= 90
            
        #if we found an angle that is too extreme it's probably not right, just set to 0
        skew_angle = bounding_box_rotation if abs(bounding_box_rotation) < max_rotation else 0
        print("skew", skew_angle, ": ", bounding_box_rotation)

        # skew full original image and bounding box to align slightly misalgned cards
        skew_matrix = cv2.getRotationMatrix2D(rect[0], skew_angle, 1.0)
        skewed_original_image = cv2.warpAffine(img, skew_matrix, (original_image_width, original_image_height))
        skewed_bounding_box_points = cv2.transform(np.array([bounding_box_points]), skew_matrix)[0]

        # Reduce to min/max points
        bb_x1, bb_y1 = skewed_bounding_box_points.min(axis=0)
        bb_x2, bb_y2 = skewed_bounding_box_points.max(axis=0)
        bb_x1 = max(int(bb_x1) - buffer, 0)
        bb_y1 = max(int(bb_y1) - buffer, 0)
        bb_x2 = min(int(bb_x2) + buffer, skewed_original_image.shape[1])
        bb_y2 = min(int(bb_y2) + buffer, skewed_original_image.shape[0])

        # Perform the final crop on the skewed image
        final_crop = skewed_original_image[bb_y1:bb_y2, bb_x1:bb_x2]
        # Use final image height for coordinate rotation
        final_crop_height = final_crop.shape[0]

        # Rotate final crop if width > height so that we can ensure we're working on a portrait
        #why do we do this at the top and bottom?
        portrait_img = img.copy()
        final_crop_height = portrait_img.shape[0]
        
        if final_crop.shape[1] > final_crop.shape[0]:
            
            final_crop = cv2.rotate(final_crop, cv2.ROTATE_90_CLOCKWISE)
            portrait_img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

            def rotate_point(x, y, height):
                return height - y - 1, x

            rotated_points = np.array([rotate_point(x, y, final_crop_height) for x, y in skewed_bounding_box_points])

            #Now switch to using portrait img
            # Crop rotated bounding box from rotated image
            bb_x1, bb_y1 = rotated_points.min(axis=0)
            bb_x2, bb_y2 = rotated_points.max(axis=0)

            bb_x1 = max(int(bb_x1) - buffer, 0)
            bb_y1 = max(int(bb_y1) - buffer, 0)
            bb_x2 = min(int(bb_x2) + buffer, portrait_img.shape[1])
            bb_y2 = min(int(bb_y2) + buffer, portrait_img.shape[0])


        # Check if aspect ratio is too extreme — fallback if so
        aspect = final_crop.shape[1] / final_crop.shape[0] if final_crop.shape[0] else 0
        if aspect > 3.0 or aspect < 0.3:
            print("⚠️ Cropped region has unusual aspect ratio — reverting to original image.")
            final_crop = img.copy()
            crop_params = None
        else:
            crop_params = CropParams.objects.create(x=bb_x1, y=bb_y1, width=bb_x2-bb_x1, height=bb_y2-bb_y1, rotate=float(skew_angle))
            crop_params.save()
            print("Cp:",  crop_params)
        
        # Encode as jpg
        success, buffer = cv2.imencode(".jpg", final_crop)
        if not success:
            raise ValueError("Image encoding failed.")
        django_file = ContentFile(buffer.tobytes())

        
        #encode the new portrait image
        success, encoded_image = cv2.imencode('.jpg', portrait_img)
        if success:
            portrait_django_file = ContentFile(encoded_image.tobytes())
        else:
            raise ValueError("Failed to encode portrait image")      

        return django_file, portrait_django_file, crop_params
    
    def parse_and_tokenize_search_results(self, items):
        csr = CardSearchResult.from_search_results(self, items)

        return csr

    def retokenize(self, csr_id):
        csr = CardSearchResult.objects.get(id=csr_id)
        return csr.retokenize()

    #obviously all needs to be cleaned up
    def update_crop(self, cropped_image, is_reverse, crop_x=0, crop_y=0, crop_width=0, crop_height=0, display_left_offset=0, display_top_offset=0, canvas_rotation=0.0):
        """
        Update the crop parameters based on the latest loaded image.
        """
        
        
        square_rotation = round(canvas_rotation/90)*90
        remainder_rotation = canvas_rotation-square_rotation
        square_rotation = square_rotation%360
        print(f"Squared rotation: {square_rotation}, {remainder_rotation} degrees")
        
        last_csr = self.active_search_results()

        if is_reverse:
            crop_params = last_csr.reverse_crop_params
            target_image = self.cropped_reverse
            portrait_image = self.portrait_reverse
        else:
            crop_params = last_csr.front_crop_params
            target_image = self.cropped_image
            portrait_image = self.portrait_image

        crop_params.x = crop_x
        crop_params.y = crop_y
        crop_params.width = crop_width
        crop_params.height = crop_height
        crop_params.display_left_offset = display_left_offset
        crop_params.display_top_offset = display_top_offset
        crop_params.rotate = remainder_rotation
        crop_params.save()
        print("Daniel", crop_params)
        #print(last_csr.crop_params)
        target_image.update(content=cropped_image, crop_params=crop_params)
        
        #not sure I'm happy doing this here, but it works for now
        #at the very least abstract this into another method
        file_bytes = np.asarray(bytearray(portrait_image.img.file.read()), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if square_rotation > 0:
            rotation_map = {
                90: cv2.ROTATE_90_CLOCKWISE,
                180: cv2.ROTATE_180,
                270: cv2.ROTATE_90_COUNTERCLOCKWISE
            }
        
            cv_rotation = rotation_map.get(square_rotation, None)
            
            # Now apply rotation
            rotated_portrait = cv2.rotate(image, cv_rotation)

            success, buffer = cv2.imencode(".jpg", rotated_portrait)
            if not success:
                raise ValueError("Failed to encode image")

            # Step 2: Convert buffer to bytes
            image_bytes = buffer.tobytes()
            content_file = ContentFile(image_bytes)
            portrait_image.update(content=content_file, crop_params=crop_params)

        self.save()  # Save the updated crop parameters to the database

    
