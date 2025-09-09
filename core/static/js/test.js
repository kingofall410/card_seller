document.addEventListener("DOMContentLoaded", () => {
    console.log("🚀 DOM ready — initializing crappers");
    console.log("really")
    
    const targets = document.querySelectorAll(".cropper-target");
    targets.forEach(img => {
        const cardId = img.dataset.cardId;
        const saveBtn = document.getElementById(`save-btn-${cardId}`);
        const rotateCWBtn = document.getElementById(`rotate-cw-${cardId}`);
        const rotateCCWBtn = document.getElementById(`rotate-ccw-${cardId}`);
        const rotate1CWBtn = document.getElementById(`rotate-1cw-${cardId}`);
        const rotate1CCWBtn = document.getElementById(`rotate-1ccw-${cardId}`);
        console.log(`Starting loop for ${cardId}`)
        
        let cropper, currentRotation=0;
        console.log(img)
        if (img.dataset.bound === "true") {
            console.log(`⏭️ Skipping not starting already-bound cropper: ${cardId}`);
            return;
        }

        img.dataset.bound = "true"

        const starting_crop = window[`starting_crop_${cardId}`];
        const initCropper = () => {
            let imageData, containerData;
            let canvasBefore, canvasAfter;
            let scaleX, scaleY, offsetX, offsetY;
            let cropCenterX, cropCenterY, canvasCenterX, canvasCenterY;
            
            //img.style.display = "block";
            //alert(img)
            //console.log("Image src:", img.src);
            //console.log("Image naturalWidth:", img.naturalWidth, "naturalHeight:", img.naturalHeight);
            
            cropper = new Cropper(img, {
                viewMode: 0,
                autoCrop: true,
                autoCropArea: 1.0,
                responsive: false,
                dragMode: 'none',
                zoomable: false,
                ready() {
                    console.log(`🎯 Cropper ready for card ${cardId}`);
                    img.dataset.bound = "true";
                    
                    //grab the cropper start state
                    imageData = cropper.getImageData();
                    containerData = cropper.getContainerData();
                    console.log("cd:,", containerData)
                    //calculate REVERSE canvas and crop-box transformations
                    scaleX = imageData.width / imageData.naturalWidth;
                    scaleY = imageData.height / imageData.naturalHeight;
                    cropCenterX = imageData.left + starting_crop.x * scaleX + (starting_crop.width * scaleX) / 2;
                    cropCenterY = imageData.top + starting_crop.y * scaleY + (starting_crop.height * scaleY) / 2;
                    canvasCenterX = containerData.width / 2;
                    canvasCenterY = containerData.height / 2;
                    offsetX = canvasCenterX - cropCenterX;
                    offsetY = canvasCenterY - cropCenterY;               
                    
                    canvasBefore = {
                        left: imageData.left + offsetX,
                        top: imageData.top + offsetY,
                        width: imageData.width,
                        height: imageData.height
                    };
                    
                    //UNDO whatever cropper did to the canvas
                    cropper.setCanvasData(canvasBefore);
                    console.log("Canvas Before:", cropper.getCanvasData());
                    console.log("crop:", starting_crop);

                    //rotate around origin
                    cropper.rotateTo(-starting_crop.rotate);
                    currentRotation = -starting_crop.rotate
                    //translate back to original cropped positioning
                    const parsedLeft = parseFloat(starting_crop.canvasLeft);
                    const parsedTop = parseFloat(starting_crop.canvasTop);
                    console.log(parsedLeft, parsedTop)
                    //reset to original
                    const originalCanvas = {
                        left: parsedLeft,
                        top: parsedTop,
                        width: imageData.width,
                        height: imageData.height                            
                    }
                    if (!isNaN(parsedLeft) && !isNaN(parsedTop)) {                        
                        console.log("set back")
                        cropper.setCanvasData(originalCanvas);                        
                    }

                    
                    console.log(imageData)
                    console.log(originalCanvas)
                    console.log(containerData)
                    console.log("fuck you", img)

                    console.log("crapper:", cropper);
                    if (cropper && typeof cropper.getCanvasData === 'function') {
                        canvasAfter = cropper.getCanvasData();
                        console.log("Canvas After:", canvasAfter);
                    } else {
                        console.warn("Cropper unstable or not fully initialized:", cropper);
                    }                  
                                    
                    console.log("cd:", containerData)
                    console.log("id:", imageData)                    
                    console.log("id:", starting_crop)
                    console.log("scale:", scaleX, scaleY)
                    console.log("offset:", offsetX, scaleY)
                    
                    console.log("cb", canvasBefore)
                    console.log("ca", canvasAfter)
                    let deltaX = (canvasBefore.left-canvasAfter.left)
                    let deltaY = (canvasBefore.top-canvasAfter.top)

                    console.log("deta:", deltaX, deltaY)
                    const cropBoxData = {
                        left: starting_crop.x * scaleX + imageData.left + offsetX - deltaX - parsedLeft,
                        top: starting_crop.y * scaleY + imageData.top + offsetY - deltaY - parsedTop,
                        width: starting_crop.width * scaleX,
                        height: starting_crop.height * scaleY
                    };
                    console.log("Crop Box Data:", cropBoxData);

                    cropper.setCanvasData(canvasAfter);
                    cropper.setCropBoxData(cropBoxData);

                    console.log("CropBox:", cropper.getCropBoxData());
                }
            });
            
        };
        rotateCWBtn.addEventListener("click", function () {
            console.log("cw")
            currentRotation = (currentRotation + 90) % 360;
            cropper.rotateTo(currentRotation);
        });

        rotateCCWBtn.addEventListener("click", function () {
            console.log("ccw")
            currentRotation = (currentRotation + 270) % 360;
            cropper.rotateTo(currentRotation);
        });
        rotate1CWBtn.addEventListener("click", function () {
            console.log("cw")
            currentRotation = (currentRotation + 1) % 360;
            cropper.rotateTo(currentRotation);
        });

        rotate1CCWBtn.addEventListener("click", function () {
            console.log("ccw")
            currentRotation = (currentRotation + 359) % 360;
            cropper.rotateTo(currentRotation);
        });
        saveBtn.addEventListener("click", function () {
            
            save(cropper, cardId, saveBtn)
        });
        if (img.complete && img.naturalWidth !== 0) {
            console.log(`✅ Image already loaded: ${cardId}`);
            console.log("🧪 Tag name:", img);

            initCropper();
        } else {
            img.onload = () => {
                console.log(`📸 Image loaded for card ${cardId}`);
                initCropper();
            };
        }
    })

});
//TODO: probably want to make this a multi call at some point
async function save(cropper, cardId, btn) {
    console.log("Saving crop data...", cropper);

    const canvas = cropper.getCroppedCanvas();
    if (!canvas) {
        console.error("❌ No canvas available for cropping.");
    return;
    }

    btn.classList.add("button-waiting");

    try {
    const blob = await new Promise((resolve) =>
        canvas.toBlob(resolve, "image/jpeg")
    );
    if (!blob) throw new Error("Failed to generate blob from canvas.");

    const imageData = cropper.getImageData();
    const savedCanvas = cropper.getCanvasData();
    const savedCropBox = cropper.getCropBoxData();

    const scaleX = imageData.naturalWidth / imageData.width;
    const scaleY = imageData.naturalHeight / imageData.height;

    const formData = new FormData();
    formData.append("cropped_image", blob, "cropped.jpg");
    formData.append("card_id", cardId);
    formData.append("crop_left", (savedCropBox.left - imageData.left) * scaleX);
    formData.append("crop_top", (savedCropBox.top - imageData.top) * scaleY);
    formData.append("crop_width", savedCropBox.width * scaleX);
    formData.append("crop_height", savedCropBox.height * scaleY);
    formData.append("canvas_rotation", -imageData.rotate);
    formData.append("canvas_left", savedCanvas.left);
    formData.append("canvas_top", savedCanvas.top);

    const response = await fetch("/upload_crop/", {
        method: "POST",
        body: formData,
    });

    const data = await response.json();
    const croppedPreview = document.getElementById(`cropped-${cardId}`);

    if (data.status === "saved" && data.url && croppedPreview) {
        console.log("✅ Saved successfully");
        croppedPreview.src = data.url;
    } else {
        console.warn("⚠️ Unexpected response:", data);
    }
    } catch (error) {
        console.error("❌ Save error:", error);
    } finally {
        btn.classList.remove("button-waiting");
    }
}
