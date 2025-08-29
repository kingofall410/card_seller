import os, json
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from .display import generate_index_from_directory  # assuming display.py is in core
from django.core.files.storage import default_storage
from services import lookup
from services import export as export_handler
from django.utils.timezone import now
from django.db import models
from services import settings_management as app_settings
from services import text
from services import photo_manip as photo
from services.models import Settings, Condition, Team, City, CardAttribute, Brand, Subset, KnownName, Parallel
from core.models.Card import Card, Collection
from core.models.CardSearchResult import CardSearchResult
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.urls import reverse
from django.db.models import F

from urllib.parse import unquote


BASE_DIR = os.path.join(settings.BASE_DIR)  # example folder

def hello_world(request):
    
    return render("success.html")

def test_view(request):

    conditions = Condition.objects.all().delete()
    



def crop_review(request, card_id):
    card = get_object_or_404(Card, id=card_id)
    return render(request, "crop_review.html", {"card": card, "search_results":card.active_search_results()})

def save_and_next(request, card_id):
    if request.method == "POST":
        upload_crop(request)
        return next(request, card_id)

def next(request, card_id):
    if request.method == "POST":
        # Save logic here
        delta = 1
        if card_id[0] == '-':
            delta = -1
            
        next_card_id =card_id + delta
        
        return redirect("crop_review", card_id=next_card_id)
    
def save_overrides(request, card_id=None, csr_id=None):
    print(f"saveOverrides: {card_id}")
    card = get_object_or_404(Card, pk=card_id)
    csr = card.active_search_results()
    if csr_id:
        csr = get_object_or_404(CardSearchResult, pk=csr_id)       

    for field in csr.overrideable_fields:
    
        manual_flag = f"{field}_is_manual"
        manual_val = f"{field}_m"

        # Handle manual toggle checkbox
        is_manual = request.POST.get(manual_flag) == "on"
        print(f"setting {manual_flag} to {is_manual}")
        setattr(csr, manual_flag, is_manual)

        # Handle manual value input
        if manual_val in request.POST:
            print(f"setting {manual_val} to {request.POST.get(manual_val)}")
            setattr(csr, manual_val, request.POST.get(manual_val))

    csr.save()
    return JsonResponse({"status": "success"})

@csrf_exempt
def view_collection(request, collection_id=None):
    cards = []
    if collection_id:
        collection = Collection.objects.get(id=collection_id)
        cards = collection.cards.all()
    else:
        cards = Card.objects.order_by('-id')

    settings = Settings.objects.first()  # or however you fetch it
    
    cards = [(card, card.active_search_results()) for card in cards]
    paginator = Paginator(cards, settings.nr_collection_page_items)
    
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "collection.html", {"page_obj": page_obj, "collection_id":collection.id})

@csrf_exempt    
def view_card(request, card_id):
    if card_id:
        card = Card.objects.get(id=card_id)
        
    return render(request, "card.html", {"card": card, "search_results":card.active_search_results()})


@csrf_exempt
def add_token(request):
    print("body", request.body)
    if request.method == 'POST':
        data = json.loads(request.body)
        field_key = data.get("field_key")
        new_value = data.get("token", "")
        allFields = data.get("fields", {})

        print(f"add_token: {field_key}: {new_value}")
        print(allFields)

        if app_settings.add_token(field_key, new_value, allFields):
            return JsonResponse({"success": True, "error": ""})
    return JsonResponse({"error": True, "error": "Failed to add token"})

@csrf_exempt
def get_dynamic_options(request):
    print(request.body)
    options = []
    indie_options = []
    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        term = data.get("term", "")
        field_key = data.get("field", "")
        csr_id = data.get("csrId", "")

        filter_kwargs = {"raw_value__icontains": term}
        #TODO: this is naive and replicates logic in custom_tags.py
        #TODO: need to find a betyter way to differentiate between tokens and more complicated fields (#s)
        #TODO: ultimately I need to implement serialnr, year, etc
        if field_key == "brands" or field_key == CardSearchResult.stupid_map("brands"):
            options = list(
                Brand.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )

            if csr_id:
                indie_options = CardSearchResult.objects.get(id=csr_id).get_individual_options("brands")
            #[obj.raw_value for obj in Brand.objects.order_by("raw_value")]
        elif field_key == "subsets" or field_key == CardSearchResult.stupid_map("subsets"):
            options = list(
                Subset.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
            if csr_id:
                indie_options = CardSearchResult.objects.get(id=csr_id).get_individual_options("subsets")
            #return [(obj.parent_brand.raw_value, obj.raw_value) for obj in Subset.objects.order_by("raw_value")]
        elif field_key == "names" or field_key == CardSearchResult.stupid_map("names"):
            options = list(
                KnownName.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
            if csr_id:
                indie_options = CardSearchResult.objects.get(id=csr_id).get_individual_options("names")
            #return [obj.raw_value for obj in KnownName.objects.order_by("raw_value")]
        elif field_key == "teams" or field_key == CardSearchResult.stupid_map("teams"):
            options = list(
                Team.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
            if csr_id:
                indie_options = CardSearchResult.objects.get(id=csr_id).get_individual_options("teams")
            #return [obj.raw_value for obj in Team.objects.order_by("raw_value")]
        elif field_key == "cities" or field_key == CardSearchResult.stupid_map("cities"):
            options = list(
                City.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
            if csr_id:
                indie_options = CardSearchResult.objects.get(id=csr_id).get_individual_options("cities")
            #return [obj.raw_value for obj in City.objects.order_by("raw_value")]
        elif field_key == "attribs" or field_key == CardSearchResult.stupid_map("attribs"):
            options = list(
                CardAttribute.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
            #return [obj.raw_value for obj in CardAttribute.objects.order_by("raw_value")]
        elif field_key == "condition" or field_key == CardSearchResult.stupid_map("condition"):
            options = list(
                Condition.objects.filter(
                    ebay_id_value__isnull=False
                ).exclude(ebay_id_value="").filter(**filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
        elif field_key == "parallel" or field_key == CardSearchResult.stupid_map("parallel"):
            options = list(
                Parallel.objects.filter(primary_token_id=F("id"), **filter_kwargs)
                .values_list("raw_value", flat=True)
                .distinct()[:50]
            )
            #return [obj.raw_value for obj in Parallel.objects.order_by("raw_value")]
        elif field_key == "cardnr" or field_key == CardSearchResult.stupid_map("cardnr"):
            pass#no autocomplete for cardnr
            #options = list(CardSearchResult.objects.get(id=csr_id).get_individual_options("cardnr"))
        elif field_key == "serial_number" or field_key == CardSearchResult.stupid_map("serial_number"):
            pass#no autocomplete for serial_number
            #options = list(CardSearchResult.objects.get(id=csr_id).get_individual_options("serial_number"))
        elif field_key == "year" or field_key == CardSearchResult.stupid_map("year"):
            pass#no autocomplete for year
           #options = list(CardSearchResult.objects.get(id=csr_id).get_individual_options("year"))
        if not field_key:
            return JsonResponse([], safe=False)
        
    seen = set()
    ordered_options = []

    indie_set = set(indie_options)
    seen = set()
    ordered_options = []

    # Add indie options first
    for val in indie_options:
        if val not in seen:
            ordered_options.append({
                "label": val,
                "value": val,
                "is_indie": True,
                "disabled": not val.lower().startswith(term.lower())  # basic match logic
            })
            seen.add(val)

    # Insert divider
    ordered_options.append({
        "label": "---",
        "value": "__divider__",
        "is_divider": True
    })

    # Add non-indie options
    for val in options:
        if val not in seen:
            ordered_options.append({
                "label": val,
                "value": val,
                "is_indie": False,
                "disabled": False
            })
            seen.add(val)

    return JsonResponse(ordered_options, safe=False)



@csrf_exempt
def update_collection(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)

    collection_id = request.POST.get("collectionId")
    if not collection_id or not collection_id.isdigit():
        return JsonResponse({"error": True, "message": "Missing or invalid collectionId"}, status=400)

    try:
        collection = Collection.objects.get(id=int(collection_id))
    except Collection.DoesNotExist:
        return JsonResponse({"error": True, "message": f"Collection with id {collection_id} not found"}, status=404)

    new_name = request.POST.get("name", "").strip()
    if not new_name:
        return JsonResponse({"error": True, "message": "Missing collection name"}, status=400)

    collection.name = new_name
    collection.save()
    return JsonResponse({"success": True, "message": "Collection updated successfully"})

@csrf_exempt
def update_csr_fields(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)

    csr_id = request.POST.get("csrId")
    if not csr_id or not csr_id.isdigit():
        return JsonResponse({"error": True, "message": "Missing or invalid csrId"}, status=400)

    try:
        csr = CardSearchResult.objects.get(id=int(csr_id))
    except CardSearchResult.DoesNotExist:
        return JsonResponse({"error": True, "message": f"CardSearchResult with id {csr_id} not found"}, status=404)

    # Convert POST data to dict and sanitize
    field_data = request.POST.dict()
    field_data.pop("csrId", None)  # Remove csrId from field data
    field_data.pop("csrfmiddlewaretoken", None)  # Remove CSRF token

    # Coerce boolean fields
    for key, value in field_data.items():
        field = csr._meta.get_field(key) if key in [f.name for f in csr._meta.fields] else None
        if isinstance(field, models.BooleanField):
            field_data[key] = value.lower() in ["true", "1", "yes"]

    try:
        csr.update_fields(field_data)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": True, "message": f"Update failed: {str(e)}"}, status=500)


def manage_collection(request):
    collections = Collection.objects.order_by('-id')
    return render(request, "manage_collection.html", {"root_collections": collections})

@csrf_exempt
def image_search(request, card_id):
    print("image_search")
    if not card_id:
        return JsonResponse({'error': 'Card ID is required'}, status=400)
    card = Card.objects.get(id=card_id)
    search_results = lookup.single_image_lookup(card)
    if search_results:
        return JsonResponse({"success": True, "error": ""})
    
    return JsonResponse({"error": True, "error": "No results"})


@csrf_exempt
def image_search_collection(request, collection_id):
    print("image_search")
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    collection = Collection.objects.get(id=collection_id)
    for card in collection.cards.all():
        lookup.single_image_lookup(card)
    
    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def retokenize(request, csr_id):
    print("retokenize")

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    csr.retokenize()

    return JsonResponse({"success": True, "error": ""})


@csrf_exempt
def delete(request):
    print("delete", request)
    if request.method == 'POST':
        print("POST")
        card_id = request.POST.get('card_id')
        collection_id = request.POST.get('collection_id')
        try:

            if card_id:
            
                card = Card.objects.get(id=card_id)
                card.delete()

            if collection_id:
                collection = Collection.objects.get(id=collection_id)
                collection.delete()
        except (Collection.DoesNotExist, Card.DoesNotExist):
            return JsonResponse({'error': 'Card/Collection not found'}, status=404)
            
        
    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def export(request, csr_id):
    settings = Settings.objects.first()

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    
    success = export_handler.export_to_ebay([csr])
    if not success:
        return JsonResponse({'error': 'Need auth', 'url':settings.ebay_user_auth_consent}, status=404)
    return export_handler.export_to_ebay([csr])

@csrf_exempt
def export_collection(request, collection_id):
    print("export collection")
    settings = Settings.objects.first()

    if not collection_id or collection_id == 'undefined':
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    collection = Collection.objects.get(id=collection_id)
    csrs = collection.get_default_exports()

    return export_handler.export_zip(csrs)

@csrf_exempt
def text_search(request, card_id):
    print("text search")
    if not card_id:
        return JsonResponse({'error': 'Card ID is required'}, status=400)
    card = Card.objects.get(id=card_id)
    search_results = lookup.single_text_lookup(card) 
    if search_results:
        return JsonResponse({"success": True, "error": ""})
    
    return JsonResponse({"error": True, "error": "No results"})


@csrf_exempt
def text_search_collection(request, collection_id):
    print("text search")
    if not collection_id:
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    collection = Collection.objects.get(id=collection_id)
    for card in collection.cards:
        lookup.single_text_lookup(card)
    
    return JsonResponse({"success": True, "error": ""})
             
@csrf_exempt             
def upload_image(request, collection_id=None):
    if request.method == 'GET':
        if collection_id:
            collection = Collection.objects.get(id=collection_id)
        else:
            collection = Collection.objects.create()

    if request.method == 'POST':
     
        uploaded_files = sorted(request.FILES.getlist('images'), key=lambda r: r.name)
        collection_id = request.POST.get('collection_id')
        print(len(uploaded_files)," files")
        print("collection_id1: ", collection_id)
        if collection_id == "__Add__":
            collection = Collection.objects.create()
            collection_id = collection.id
        else:
            collection = Collection.objects.get(id=collection_id)        
        
        return_cards = []
        if len(uploaded_files) > 0:
            timestamp_folder = now().strftime("%Y%m%d_%H%M%S/")  # e.g., '20250701_125342'

            uploaded_file_paths = []

            for uploaded_file in uploaded_files:
                filename = uploaded_file.name
                print(f"📂 Uploaded filename: {filename}")

                relative_path = default_storage.save(timestamp_folder + filename, uploaded_file)
                absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                print("📎 File path:", relative_path, "| Absolute:", absolute_path)

                uploaded_file_paths.append(absolute_path)

            # 🔍 Phase 2: Process files after all uploads complete
            skip_next = False
            for absolute_path in uploaded_file_paths:
                if skip_next:
                    skip_next = not skip_next
                else:
                    source_card, skip_next = Card.from_filename(collection, absolute_path, crop=True, match_back=True)

                    lookup.single_image_lookup(source_card, "")
                    return_cards.insert(0, source_card)

            return JsonResponse({"success": True, "error": ""})
                           
    return render(request, "upload_image.html", {"collection_id":collection.id})

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

        # Redirect to the local static file served from Django or a static route
        return redirect(f"/media/{temp_dir}/index.html")  # Adjust path as needed

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


        if os.path.exists(index_file):
            return render(request, "index.html")
        else:
            return HttpResponse("⚠️ Index generation failed or is incomplete.")

        return redirect(f"/media/uploaded_run/index.html")  # Must be served as static or media

    return render(request, "select_directory.html")

def view_settings(request):
    settings = Settings.objects.first()
    return render(request, "core_settings.html", {"settings": settings})


def load_file(request):
    if request.method == "POST" and request.FILES.get("file"):
        uploaded_file = request.FILES["file"]
        file_name = uploaded_file.name

        # Save to MEDIA_ROOT/temp_uploads/
        upload_dir = "temp_uploads"
        saved_path = default_storage.save(os.path.join(upload_dir, file_name), uploaded_file)
        absolute_path = os.path.join(settings.MEDIA_ROOT, saved_path)

        #photo.crop_and_align_card(

        return render(request, "load_file.html", {"file_path": saved_path})  # optional response

    return render(request, "load_file.html")

def update_settings(request):
    print(request.body)
    if request.method == 'POST':

        nr_returned_listings = request.POST.get('nr_returned_listings')
        nr_collection_page_items = request.POST.get('nr_collection_page_items')
        field_pct_threshold = request.POST.get('field_pct_threshold')
        ebay_user_auth_consent = request.POST.get('ebay_user_auth_consent')
        ebay_auth_code_unescaped = request.POST.get('ebay_auth_code_unescaped')
        settings = Settings.objects.first()  # or however you fetch it
        settings.nr_returned_listings = nr_returned_listings
        settings.nr_collection_page_items = nr_collection_page_items
        settings.field_pct_threshold = field_pct_threshold
        settings.ebay_user_auth_consent = ebay_user_auth_consent
        settings.ebay_auth_code_unescaped = ebay_auth_code_unescaped
        settings.ebay_user_auth_code = unquote(ebay_auth_code_unescaped)
        settings.save()
    return redirect('settings')

@csrf_exempt
def collection_create(request):

    try:            
        parent_collection_id = request.POST.get('collection_id')    
        parent_collection = Collection.objects.get(id=parent_collection_id)
        new_collection = Collection.objects.create(parent_collection=parent_collection)
    
    except Collection.DoesNotExist:
        return JsonResponse({'error': 'Collection not found'}, status=404)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def settings_file_upload(request, file_type):
    uploaded_files = request.FILES.getlist("file")
    
    if not uploaded_files:
        return JsonResponse({"success": False, "error": "No files provided"})
    
    errors = []
    
    for uploaded_file in uploaded_files:
        try:
            print(request)
            #use filename as token type if possible
            base_name = uploaded_file.name
            file_type = base_name.split('.')[0]  # or use os.path.splitext(base_name)[0]
            print(base_name, file_type)
            app_settings.load_settings_file(uploaded_file, file_type)
        except Exception as e:
            errors.append(f"{uploaded_file.name}: {str(e)}")
    
    if errors:
        return JsonResponse({"success": False, "error": "; ".join(errors)})
    
    return JsonResponse({"success": True, "error": ""})

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
            instance.update_crop(img_file, is_reverse, crop_left, crop_top, crop_width, crop_height, crop_canvas_left, crop_canvas_top, canvas_rotation)
        except Card.DoesNotExist:
            return JsonResponse({'error': 'Card not found'}, status=404)
        
        

        return JsonResponse({'status': 'saved'})
    return JsonResponse({'error': 'no image'}, status=400)

@csrf_exempt
def register_field(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        search_fields = data.get('search_fields')
        field_name = data.get('field_name')
        new_value = data.get('new_value')
        card_id = data.get('card_id')

        # Do something with the data
        print(f'{card_id} Registered "{search_fields}" as "{field_name}" ({new_value})')

        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Invalid request'}, status=400)
