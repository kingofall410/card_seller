import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings as app_settings
from django.core.files.storage import default_storage
from django.utils.timezone import now
from services import lookup
from services.models import Settings 
from core.models.Card import Card, Collection
from django.views.decorators.csrf import csrf_exempt

# Image-related views
def perform_upload(uploaded_files, collection=None):
    
    if not collection:
        collection = Collection.objects.get(is_default=True)

    if len(uploaded_files) > 0:
        timestamp_folder = now().strftime("%Y%m%d_%H%M%S/")  # e.g., '20250701_125342'

        uploaded_file_paths = []
        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            print(f"📂 Uploaded filename: {filename}")
            relative_path = default_storage.save(timestamp_folder + filename, uploaded_file)
            absolute_path = os.path.join(app_settings.MEDIA_ROOT, relative_path)
            print("📎 File path:", relative_path, "| Absolute:", absolute_path)
            uploaded_file_paths.append(absolute_path)
        
        # 🔍 Phase 2: Process files after all uploads complete
        skip_next = False
        settings = Settings.get_default()
        for absolute_path in uploaded_file_paths:
            print("FP", uploaded_file_paths)
            if skip_next:
                skip_next = not skip_next
                print("Skipping")
            else:
                print("not skipping")
                source_card, skip_next = Card.from_filename(collection, absolute_path, crop=True, match_back=True)
                print("2")
                lookup.single_image_lookup(source_card, {}, settings, scrape_sold_data=False, result_count_max=settings.id_listings)

@csrf_exempt
def upload_image(request, collection_id=None):
    if request.method == 'GET':
        if collection_id:
            collection = Collection.objects.get(id=collection_id)
        else:
            collection = Collection.objects.create()
        return render(request, "upload_image.html", {"collection_id":collection.id})
    
    if request.method == 'POST':
        uploaded_files = sorted(    request.FILES.getlist('images'), key=lambda r: r.name)
        collection_id = request.POST.get('collection_id')
        print(len(uploaded_files)," files")
        print("collection_id1: ", collection_id)
        if collection_id == "__Add__":
            collection = Collection.objects.create()
            collection_id = collection.id
        else:
            collection = Collection.objects.get(id=collection_id)           
    
        perform_upload(uploaded_files, collection)                   
        return redirect('manage_collection')




@csrf_exempt
def upload_crop(request):
    print("upload crop")
    if request.method == 'POST' and request.FILES.get('cropped_image'):
        
        img_file = request.FILES['cropped_image']

        crop_left = float(request.POST.get('crop_left', 0))
        crop_top = float(request.POST.get('crop_top', 0))
        crop_width = float(request.POST.get('crop_width', 0))
        crop_height = float(request.POST.get('crop_height', 0))
        crop_canvas_left = float(request.POST.get('canvas_left', 0))
        crop_canvas_top = float(request.POST.get('canvas_top', 0))
        canvas_rotation = float(request.POST.get('canvas_rotation', 0))
        card_id = request.POST.get('card_id', None)
        print("Card: ", card_id)
        print("Crop params:", crop_left, crop_top, crop_width, crop_height)
        print("Canvas params:", crop_canvas_left, crop_canvas_top, canvas_rotation)
        
        is_reverse = False
        if not card_id:
            return JsonResponse({'error': 'Card ID is required'}, status=400)
        try:
        
            if card_id.endswith("R"):
                card_id = card_id[:-1]
                is_reverse = True
    
            instance = Card.objects.get(id=card_id)
            url = instance.update_crop(img_file, is_reverse, crop_left, crop_top, crop_width, crop_height, crop_canvas_left, crop_canvas_top, canvas_rotation)
        except Card.DoesNotExist:
            return JsonResponse({'error': 'Card not found'}, status=404)

        return JsonResponse({'status': 'saved', 'url':url})
    return JsonResponse({'error': 'no image'}, status=400)

'''
def select_directory(request):
    if request.method == "POST":
        uploaded_files = request.FILES.getlist('directory')
        temp_dir = os.path.join("temp_uploads", "run")
        os.makedirs(temp_dir, exist_ok=True)
        for file in uploaded_files:
            relative_path = file.name
            save_path = os.path.join(temp_dir, relative_path)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'wb+') as dest:
                for chunk in file.chunks():
                    dest.write(chunk)
        generate_index_from_directory(temp_dir)
        return redirect(f"/media/{temp_dir}/index.html")
    return render(request, "select_directory.html")

def upload_folder_and_redirect(request):
    if request.method == "POST":
        files = request.FILES.getlist("files")
        output_dir = os.path.join("media", "uploaded_run")
        os.makedirs(output_dir, exist_ok=True)
        for file in files:
            path = os.path.join(output_dir, file.name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            print(path)
            with open(path, "wb+") as f:
                for chunk in file.chunks():
                    f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
        index_file = os.path.join(output_dir, "index.html")
        generate_index_from_directory(output_dir)
        if os.path.exists(index_file):
            return redirect("/media/uploaded_run/index.html")
        else:
            return HttpResponse("⚠️ Index generation failed.")
    return render(request, "select_directory.html")'''
