import os
import cv2
import torch
import numpy as np
from PIL import Image
import supervision as sv

# Using Hugging Face's standard native transformers implementations for easy maintainability
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from segment_anything import sam_model_registry, SamPredictor

class GroundedSamCardExtractor:
    def __init__(self, sam_checkpoint_path="weights/sam_vit_b_01ec64.pth", box_threshold=0.15, min_card_area=4000):
        """
        Initializes the complete computer vision pipeline.
        
        :param sam_checkpoint_path: Path to downloaded SAM weights (ViT-B variant).
        :param box_threshold: GroundingDINO text confidence floor.
        :param min_card_area: Minimum pixel footprint to prevent cropping dust/fragments.
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        # Optimized defaults for mixed screenshot/pile testing
        self.box_threshold = box_threshold
        self.min_card_area = min_card_area
        
        print(f"[DEBUG] Initializing Model Pipelines. Compute target allocated to: {self.device}")
        
        # 1. Boot up Zero-Shot Language Detector (GroundingDINO)
        dino_model_id = "IDEA-Research/grounding-dino-tiny"
        self.dino_processor = AutoProcessor.from_pretrained(dino_model_id)
        self.dino_model = AutoModelForZeroShotObjectDetection.from_pretrained(dino_model_id).to(self.device)
        
        # 2. Boot up Pixel Segmentation Engine (SAM)
        if not os.path.exists(sam_checkpoint_path):
            raise FileNotFoundError(f"Missing SAM weights file at: {sam_checkpoint_path}. Please download sam_vit_b_01ec64.pth")
            
        sam_instance = sam_model_registry["vit_b"](checkpoint=sam_checkpoint_path).to(self.device)
        self.sam_predictor = SamPredictor(sam_instance)

    def process_image(self, image_path, text_prompt="card . trading card . rectangle . photo . picture .", output_dir="./extracted_crops"):
        """
        Runs full pipeline: Detects via DINO, Refines via SAM, Filters & Crops via Supervision.
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Source file target not found: {image_path}")

        # Load native source layers
        image_pil = Image.open(image_path).convert("RGB")
        image_cv = cv2.imread(image_path)
        
        # --- STAGE 1: INFER BOUNDING BOXES (GroundingDINO) ---
        print(f"[DEBUG] Prompting GroundingDINO with query: '{text_prompt}'")
        inputs = self.dino_processor(images=image_pil, text=text_prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.dino_model(**inputs)
            
        # Post-process raw results to fit original input canvas dimensions
        raw_dino_results = self.dino_processor.post_process_grounded_object_detection(
            outputs=outputs,
            input_ids=inputs.input_ids,
            target_sizes=[(image_pil.size[1], image_pil.size[0])]
        )[0]

        # Extract underlying model tensor predictions
        all_boxes = raw_dino_results["boxes"].cpu().numpy()
        all_scores = raw_dino_results["scores"].cpu().numpy()
        all_labels = raw_dino_results.get("text_labels", ["object"] * len(all_scores))
        
        # --- CRITICAL RAW OUTPUT DEBUG LOGGER ---
        print(f"\n[DEBUG LOG] --- RAW MODEL DETECTIONS FOUND: {len(all_scores)} ---")
        for idx, (score, label) in enumerate(zip(all_scores, all_labels)):
            print(f" -> Detection #{idx}: Matched Prompt Token: '{label}' | Model Score: {score:.4f}")
        print("[DEBUG LOG] -----------------------------------------\n")
        
        # Downstream filter utilizing current floor configuration
        keep_indices = all_scores >= self.box_threshold
        detected_boxes = all_boxes[keep_indices]
        confidences = all_scores[keep_indices]
        
        if len(detected_boxes) == 0:
            print(f"[WARN] Zero candidates survived the current filter threshold of: {self.box_threshold}")
            return 0

        # --- STAGE 2: INFER PIXEL SEGMENTATION MASKS (SAM) ---
        print(f"[DEBUG] Feeding {len(detected_boxes)} bounding geometries to SAM Predictor...")
        self.sam_predictor.set_image(cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB))
        
        final_masks = []
        for box in detected_boxes:
            xmin, ymin, xmax, ymax = map(int, box)
            masks, _, _ = self.sam_predictor.predict(
                box=np.array([xmin, ymin, xmax, ymax]),
                multimask_output=False
            )
            final_masks.append(masks[0])

        # --- STAGE 3: UNIFY & FILTER DATA (Supervision) ---
        detections = sv.Detections(
            xyxy=np.array(detected_boxes, dtype=np.float32),
            mask=np.array(final_masks, dtype=bool),
            confidence=np.array(confidences, dtype=np.float32)
        )

        # Apply structural spatial filter to remove small pixel dust
        detections = detections[detections.area >= self.min_card_area]
        print(f"[DEBUG] Supervision finalized {len(detections)} targets passing structural thresholds.")

        if len(detections) == 0:
            print("[WARN] No targets survived the structural size thresholds.")
            return 0

        # --- STAGE 4: WRITE CROPS TO DISK ---
        os.makedirs(output_dir, exist_ok=True)
        
        with sv.ImageSink(target_dir_path=output_dir, overwrite=False, image_name_pattern="card_{:04d}.jpg") as sink:
            for xyxy in detections.xyxy:
                cropped_card = sv.crop_image(image=image_cv, xyxy=xyxy)
                sink.save_image(image=cropped_card)

        print(f"[DEBUG] Pipeline loop complete. Snipped assets saved into: {output_dir}")
        return len(detections)


def run_pipeline_on_file(image_path, output_dir):
    """
    ADAPTED ENTRY POINT FOR DJANGO VIEWS
    Takes the paths directly from the view file handling the multipart upload.
    """
    # Using loosened thresholds for more versatile initial testing drops
    PIPELINE_ENGINE = GroundedSamCardExtractor(
        sam_checkpoint_path="/home/dcrown/card-seller/card_seller/services/weights/sam_vit_b_01ec64.pth",
        box_threshold=0.15,
        min_card_area=5000
    )
    
    # Fully expanded open-vocabulary string bounds to prevent zero-token rejection
    total_cropped = PIPELINE_ENGINE.process_image(
        image_path=image_path, 
        text_prompt="cards .", 
        output_dir=output_dir
    )
    return total_cropped

# --- CLI ENTRY TRIGGER ROUTINE ---
if __name__ == "__main__":
    # Fallback to local test file execution if run directly via command line
    print("[DEBUG] Running pipeline file locally...")
    run_pipeline_on_file(image_path="fbm6.jpg", output_dir="./cards_extracted_out")