import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings as app_settings
from django.core.files.storage import default_storage
from django.utils.timezone import now
from services import lookup
from services.models.models import Settings 
from core.models.Card import Card, Collection 
from django.views.decorators.csrf import csrf_exempt
from django.apps import apps
from core.models.Status import StatusBase

#this stuff needs to move!!!!
def upload(collection, timestamp_folder, filename, file):

    relative_path = default_storage.save(timestamp_folder + filename, file)
    absolute_path = os.path.join(app_settings.MEDIA_ROOT, relative_path)
    print("📎 File path:", relative_path, "| Absolute:", absolute_path)
    return absolute_path

def perform_id(card_id, is_slab=False):
    lookup_sites = ["psa"] if is_slab else ["ebay"]
    source_card = Card.objects.get(id=card_id)
    lookup.single_image_lookup(source_card, {}, None, sites=lookup_sites, scrape_sold_data=False, result_count_max=50)

    #temp hack to see if this works
    return source_card.successful_id()

# Image-related views
def perform_upload(uploaded_files, collection=None, is_slab=False):
    
    if not collection:
        collection = Collection.objects.create()

    if len(uploaded_files) > 0:
        timestamp_folder = now().strftime("%Y%m%d_%H%M%S/")  # e.g., '20250701_125342'

        core_config = apps.get_app_config("core")
        skip_next = False
        image_paths = []
        for uploaded_file in uploaded_files:
            filename = uploaded_file.name
            #not going to do this with a task just yet - need to deal with the file immediately?
            absolute_path = upload(collection, timestamp_folder, filename, uploaded_file)
            image_paths.append(absolute_path)           
            print(f"📂 Uploaded filename: {filename}")
        
        for absolute_path in image_paths:
            if skip_next:
                skip_next = not skip_next
            else:
                
                source_card, _ = Card.from_filename(collection, absolute_path, crop=True, match_back=True, is_slab=False)
                csr = source_card.active_search_results
                
                id_task = core_config.queue.schedule_id_task(name=f"ID image {filename}", callback=perform_id, params={"card_id":source_card.id}, card=source_card)
                core_config.queue.schedule_pricing_task(name=f"auto-price card {source_card.id}", csr=csr, card=source_card, callback=lookup.price_only_card, params={"card_id": source_card.id, "settings_id":2}, predecessor=id_task, on_success_status=StatusBase.AUTO_PRICED)
                skip_next = True

@csrf_exempt
def upload_image(request, collection_id=None):
    if request.method == 'GET':
        if collection_id and collection_id > 0:
            collection = Collection.objects.get(id=collection_id)
        else:
            collection = Collection.objects.create()
        return render(request, "upload_image.html", {"collection_id":collection.id})
    
    if request.method == 'POST':
        uploaded_files = sorted(request.FILES.getlist('images'), key=lambda r: r.name)
        collection_id = request.POST.get('collection_id')
        is_slab = (request.POST.get('slab') == 'true') or (request.POST.get('slab') == 'True')
        
        if collection_id == "0":
            collection = Collection.objects.create()
            collection.save()
            collection_id = collection.id
        else:
            collection = Collection.objects.get(id=collection_id)           
    
        perform_upload(uploaded_files, collection, is_slab=is_slab)                   
        return JsonResponse({'success': True, 'message': ''}, status=200)

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