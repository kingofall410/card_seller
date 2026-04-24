import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models.Card import Card, Collection
from core.models.Group import ProductGroup
from core.models.ListingGroup import ListingGroup
from core.models.ListedInfo import ListedInfo
from core.models.Status import StatusBase
from core.models.CardSearchResult import CardSearchResult
from core.models.Archive import CardArchive
from services.models.models import Settings
from django.db import models
from django.core.paginator import Paginator
from math import floor
from services import lookup
from django.forms.models import model_to_dict
from django.apps import apps
from django.db import connection, transaction, IntegrityError
from django.db.models import Q
from django.template.loader import render_to_string
from core.views import collection_views
from django.utils.timezone import now 
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
from django.conf import settings as app_settings
import operator
from django.core.exceptions import FieldError
from django.db.models import OuterRef, Subquery
import traceback

def build_q_from_filters(filters_json):
    if not filters_json:
        return Q()
    
    data = json.loads(filters_json)
    final_q = Q()
    op_map = {'=': 'exact', '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte', '!=': 'neq'}

    for field, items in data.items():
        field_q = Q()
        for f in items:
            op = f.get('op')
            val = f.get('val')
            
            # Logic for field mapping
            target = 'latest_status' if field == 'overall_status' else (
                field if hasattr(Card, field) else f"search_results__{field}"
            )
            
            if op == '!=':
                field_q |= ~Q(**{target: val})
            else:
                lookup = f"{target}__{op_map.get(op, 'exact')}"
                field_q |= Q(**{lookup: val})
        
        final_q &= field_q
    return final_q

@csrf_exempt
def bulk_archive(request):
    try:
        card_ids = request.POST.getlist('card_ids[]')
        if len(card_ids):
            print("lenny", len(card_ids))
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            print("no cards", len(card_ids))
            card_list = list(collection.cards.order_by('id'))
    except json.JSONDecodeError:
        card_list = list(collection.cards.order_by('id'))
    
    for card in card_list:
        CardArchive.archive(card.id)

    return JsonResponse({"success": 'true'}, status=200)

@csrf_exempt
def archive(request, card_id):
    ca = CardArchive.archive(card_id)
    #card = Card.objects.get(id=card_id)
    #card.active_search_results().collapse_token_maps()
    return JsonResponse({"success": 'true'}, status=200)

@csrf_exempt
def rehydrate(request, card_id):
    card = CardArchive.rehydrate({"original_id":card_id}, 117)

# Card-related views
@csrf_exempt
def card_test(request):
    if request.method == 'POST':
        try:
            cards = Card.objects.filter(id__gt=4102).filter(id__lt=4119).delete()
            #card = CardArchive.rehydrate(9, 117)
            
            #card.save()
            '''if not hasattr(card, 'listed_card_info'):
                li = ListedInfo.create_from_card(card)
                li.save()
            else:
                li = card.listed_card_info

            if card.active_search_results() and card.active_search_results().overall_status == StatusBase.LISTED:
                li.update_from_csr(card.active_search_results())
                li.list_price = card.active_search_results().list_price
                li.save()
            card.save()'''
            

            return JsonResponse({"success": 'true'}, status=200)
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)

# Card-related views
@csrf_exempt
def view_card(request, card_id):
    print("view_card", request.body)
    settings = Settings.get_default()
    
    if card_id:
        first_card = Card.objects.get(id=card_id)
    
    card_ids = []
    if request.method == "POST":
        try:
            card_ids = json.loads(request.POST.get('card_ids', '[]'))
        except json.JSONDecodeError:
            pass

    if len(card_ids) <= 0:
        card_list = list(first_card.collection.cards.order_by('id'))
    else:
        card_list = Card.objects.filter(id__in=card_ids).order_by('id')
    
    #print(card_list)
    if not first_card:
        first_card = card_list[0] if card_list else None

    #print("post2")
    page_number = request.GET.get('page')
        
    #at this point we know the cards in the collection and the current card
    #no page number means just go to card_id
    if not page_number and card_id and card_list:
        try:
            index = next((i for i, c in enumerate(card_list) if c.id == int(card_id)))
            page_number = floor(index) + 1
        except StopIteration:
            page_number = 1
    #print("post3")

    #above is neutered for now until paging is re-implemented

    cc_asr = first_card.active_search_results()

    #print(cc_asr.id)
    dataset_configs = []
    for group in cc_asr.listing_groups.all():
        dataset_configs.append({
            "key": f"group-{group.id}",
            "label": group.label or "Unnamed Group",
            "color": group.color,
            "borderWidth": group.border_width,
            "lineStyle": group.line_style,
            "data": group.serialize_listings(),
            "min_price": group.min_price,
            "max_price": group.max_price,
            "min_date": group.min_date.isoformat() if group.min_date else None,
            "max_date": group.max_date.isoformat() if group.max_date else None,
            "recent_date": group.recent_date.isoformat() if group.recent_date else None,
            "display_default": group.display,
            "trend_overall": group.trend_overall,
            "trend_recent": group.trend_recent,
            "overall_start_price": group.overall_start_price,
            "overall_end_price": group.overall_end_price,
            "branch_point_y": group.recent_trend_start_price,
            "rp_upper": group.relevence_filter_bounds[1],
            "rp_lower": group.relevence_filter_bounds[0],
            "unfiltered_start": group.unfiltered_start_price,
            "unfiltered_end": group.unfiltered_end_price
    
        })
        print ("start price", group.label, group.overall_start_price, group.recent_trend_start_price)

    card_tuple = (first_card, first_card.id, cc_asr, [], [], [], [], [], [], [], [], json.dumps(dataset_configs))
            
    #print(card_tuples)
    
    return render(request, "card.html", {"card_tuple": card_tuple, "collection_id": first_card.collection.id, "settings": Settings.get_default(), "filtered":first_card.collection.cards.count()-len(card_list), "card_ids":json.dumps(card_ids), "StatusBase":StatusBase})


@csrf_exempt
def crop_review(request, collection_id):
    # Standard POST retrieval
    card_ids = request.POST.getlist('card_ids')
    
    if card_ids:
        card_list = Card.objects.filter(id__in=card_ids).order_by('id')
    else:
        card_list = []

    
    card_tuples = [(card, id_) for card in card_list for id_ in (card.id, card.reverse_id) ]
    print("CR", card_tuples)
    return render(request, "crop_review.html", {"card_tuples": card_tuples})

def save_and_next(request, card_id):
    if request.method == "POST":
        upload_crop(request)
        return next(request, card_id)

def next_card(request, card_id):
    if request.method == "POST":
        # Save logic here
        delta = 1
        if card_id[0] == '-':
            delta = -1
        next_card_id = card_id + delta
        return redirect("crop_review", card_id=next_card_id)

import traceback
@csrf_exempt
def get_spreadsheet_data(request):
    if request.method == 'POST':
        try:
            card_ids = request.POST.getlist('card_ids[]') 

            # 1. Fetch the QuerySet (remove .values())
            # We keep the annotation for the URLs as they are efficient in SQL
            records = CardSearchResult.objects.filter(
                parent_card_id__in=card_ids
            ).annotate(
                front_url=Concat(Value(app_settings.MEDIA_URL), F('parent_card__cropped_image__img'), output_field=CharField()),
                reverse_url=Concat(Value(app_settings.MEDIA_URL), F('parent_card__cropped_reverse__img'), output_field=CharField()),
            ).distinct('parent_card_id')

            # 2. Build the display-value list manually
            processed_data = []
            
            # listing_fields should contain the raw field names (e.g., 'brand', 'subset')
            fields_to_process = CardSearchResult.listing_fields

            for csr in records:
                # Initialize with the already-calculated URLs
                row = {
                    'front_url': csr.front_url,
                    'reverse_url': csr.reverse_url,
                    'id': csr.id,
                }
                
                # Use your get_attribute logic for every listing field
                for field in fields_to_process:
                    if hasattr(csr, f"display_{field}"):
                        # This calls your convention: csr|get_attribute:"display_brand"
                        row[field] = getattr(csr, f"display_{field}")
                
                processed_data.append(row)

            return JsonResponse(processed_data, safe=False, status=200)

        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)

def card_search_ajax(request):
    query = request.GET.get('q', '').strip()
    since_date_str = request.GET.get('since')
    filters_json = request.GET.get('filters')
    is_update = request.GET.get('updates_only') is not None
    
    # 1. Define the Subquery to get the 'latest' overall_status
    latest_result_status = CardSearchResult.objects.filter(
        parent_card=OuterRef('pk')
    ).order_by('-id').values('overall_status')[:1]
    
    # 2. Base Query: Start with Card and annotate the latest status
    cards_queryset = Card.objects.annotate(
        latest_status=Subquery(latest_result_status)
    )
    
    # 3. Base Text Filters (The 'filters' Q object you previously defined)
    filters = Q(
        Q(search_results__full_name__icontains=query) |
        Q(search_results__year__icontains=query) |
        Q(search_results__brand__icontains=query) |
        Q(search_results__team__icontains=query) 
    )
    
    # 4. Handle Filters vs Sort
    filter_payload = json.loads(filters_json) if filters_json else {}
    
    # Separate filter data from sort data to prevent the 'sort__exact' error
    filter_only_data = {k: v for k, v in filter_payload.items() if k != 'sort'}
    
    # Build Q object for filters only
    dynamic_q = build_q_from_filters(json.dumps(filter_only_data))
    final_q = filters & dynamic_q
    
    # 5. Add modification date constraint
    if since_date_str:
        target_date = parse_datetime(since_date_str)
        if target_date:
            final_q &= Q(modification_date__gte=target_date)
            
    # Execute base filtering
    cards_list = cards_queryset.filter(final_q)
    
    # 6. Handle Sorting separately from Filtering
    sort_data = filter_payload.get('sort')
    if sort_data and isinstance(sort_data, list) and len(sort_data) > 0:
        # Expected structure: { 'val': 'field_name', 'op': 'asc'/'desc' }
        s = sort_data[0]
        field = s.get('val')
        direction = s.get('op', 'asc').lower()
        
        # Add a '-' prefix for descending, ensure field is safe
        order_prefix = '-' if direction == 'desc' else ''
        cards_list = cards_list.order_by(f"{order_prefix}{field}")
    else:
        # Default sort
        cards_list = cards_list.order_by('-id')
    
    # Use distinct to handle potential duplicates from joins
    cards_list = cards_list.distinct()
    
    print("SQL Query:", cards_list.query)
    
    # 7. UI Logic (Pagination vs Patching)
    if is_update:
        cards_to_render = cards_list
        has_next = False
        next_page = None
    else:
        paginator = Paginator(cards_list, 50)
        page_num = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_num)
        cards_to_render = page_obj
        has_next = page_obj.has_next()
        next_page = page_obj.next_page_number() if has_next else None

    # 8. Generate HTML Partial
    html = render_to_string('components/search_results_partial.html', {
        'cards': cards_to_render,
        'is_refresh': is_update
    }, request=request)

    # 9. Return JSON Response
    return JsonResponse({
        'html': html,
        'table_data': [], # Add logic here if needed
        'col_headers': CardSearchResult.listing_fields,
        'has_next': has_next,
        'next_page': next_page,
        'total_count': cards_list.count(),
        'server_time': timezone.now().isoformat()
    })
    
def get_card_item(request, card_id):
    card = get_object_or_404(Card, id=card_id)
        
    return render(request, 'components/card_item.html', {'card': card})

@csrf_exempt
def hold_card(request, csr_id):
    print("hold", csr_id)
    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    settings = Settings.get_default()
    if request.method == 'POST':
        field_data = convert_and_sanitize(request.POST.dict(), csr)
        csr.update_fields(field_data)
    csr.status = StatusBase.LOCKED
    csr.save()
    return JsonResponse({"success": 'true'}, status=200)

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

def convert_and_sanitize(field_data, csr):
    field_data.pop("csrId", None)  # Remove csrId from field data
    field_data.pop("csrfmiddlewaretoken", None)  # Remove CSRF token
    # Coerce boolean fields
    for key, value in field_data.items():
        field = csr._meta.get_field(key) if key in [f.name for f in csr._meta.fields] else None
        if isinstance(field, models.BooleanField):
            if isinstance(value, bool):
                field_data[key] = value
            else:
                field_data[key] = value.lower() in ["true", "1", "yes"]
    return field_data

@csrf_exempt
def update_csr_fields(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)
    print("here", request)
    if request.body and len(request.body) > 0 :
        data = json.loads(request.body)
        csr_id = data["csrId"]
        all_fields = data["allFields"]
        print(csr_id)
        print(all_fields)

    if not csr_id:
        return JsonResponse({"error": True, "message": "Missing or invalid csrId"}, status=400)
    try:
        csr = CardSearchResult.objects.get(id=int(csr_id))
    except CardSearchResult.DoesNotExist:
        return JsonResponse({"error": True, "message": f"CardSearchResult with id {csr_id} not found"}, status=404)
    
    # Convert POST data to dict and sanitize
    field_data = convert_and_sanitize(all_fields, csr)    
    print("sanitized", field_data)
    #overwrite the product group info to clear a broken group
    #right now this is only used by Clear group.  It will have to be improved to handle other use cases
    if "group_key" in field_data:
        csr.ebay_product_group = None
    try:
        csr.update_fields(field_data)
    except Exception as e:
        
        traceback.print_exc()
        return JsonResponse({"error": True, "message": f"Update failed: {str(e)}"}, status=500)
    
    return JsonResponse({"success": True, "search_result":model_to_dict(csr, fields=CardSearchResult.calculated_fields) })


@csrf_exempt
def refresh_lg_calcs(request, csr_id):
    lgs = ListingGroup.objects.filter(search_result_id=csr_id)
    for lg in lgs:
        lg.save()

    return JsonResponse({"success": True})

@csrf_exempt
def update_li_fields(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)

    # Read form-encoded POST data
    li_id = request.POST.get("li_id")
    fieldname = request.POST.get("field")
    fieldvalue = request.POST.get("value")

    if not li_id or not fieldname:
        return JsonResponse({"error": True, "message": "Missing parameters"}, status=400)

    try:
        listed_info = ListedInfo.objects.get(id=int(li_id))
    except ListedInfo.DoesNotExist:
        return JsonResponse({"error": True, "message": f"ListedInfo {li_id} not found"}, status=404)

    # Update the field
    if hasattr(listed_info, fieldname):
        setattr(listed_info, fieldname, fieldvalue)
        listed_info.save()
        card = listed_info.card
        asr = card.active_search_results()
        if asr.overall_status == StatusBase.PRICED:
            asr.perform_status_update(StatusBase.REVIEWED)
        card.save()
    else:
        return JsonResponse({"error": True, "message": f"Invalid field '{fieldname}'"}, status=400)

    return JsonResponse({"success": True})

def async_lg_monitor(request):
    since_str = request.GET.get('since')
    group_ids = request.GET.getlist('ids[]')
    
    if not since_str or not group_ids:
        return JsonResponse({'html': '', 'server_time': timezone.now().isoformat()})

    since_date = parse_datetime(since_str)
    
    # We only return groups that were actually modified after the refresh was clicked
    updated_groups = ListingGroup.objects.filter(id__in=group_ids, modification_date__gt=since_date)

    html_output = ""
    for group in updated_groups:
        html_output += render_to_string('product_listings.html', {
            'listing_group': group
        }, request=request)

    return JsonResponse({
        'html': html_output,
        'server_time': timezone.now().isoformat()
    })

#this method is fudged
def render_single_card(request, card_id):
    """
    Returns the HTML partial for a single card to be swapped into the grid.
    """
    card = get_object_or_404(Card, id=card_id)
    
    # Context should match what your main grid loop uses
    context = {
        'card': card,
        # If your status_badge logic requires specific task data:
        'id_task': card.get_latest_id_task(), 
        'pricing_task': card.get_latest_pricing_task(),
        'listing_task': card.get_latest_listing_task(),
    }
    
    return render(request, 'components/card_item_partial.html', context)

@csrf_exempt
def retokenize(request, csr_id):
    print("retokenize")

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    csr.retokenize()

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def async_price_card(request, csr_id):  

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)
    csr = CardSearchResult.objects.get(id=csr_id)
    card = csr.parent_card

    core_config = apps.get_app_config("core")
    core_config.queue.schedule_pricing_task(name=f"price card {card.id}", csr=csr, card=card, callback=lookup.price_only_card, params={"card_id": card.id, "settings_id":2}, on_success_status=StatusBase.PRICED)

    return JsonResponse({"success": True, "error": ""})


@csrf_exempt
def async_price_search(request, lg_id):  

    if not lg_id or lg_id == 'undefined':
        return JsonResponse({'error': 'LG ID is required'}, status=400)
    listing_group = ListingGroup.objects.get(id=lg_id)
    csr = listing_group.search_result
    card = csr.parent_card
    
    core_config = apps.get_app_config("core")
    core_config.queue.schedule_pricing_task(name=f"price card {card.id}", csr=csr, card=card, callback=lookup.refresh_listing_groups, params={"lg_ids":[lg_id]}, on_success_status=StatusBase.PRICED)

    return JsonResponse({"success": True, "error": ""})


@csrf_exempt
def new_group(request, name):  
    clean_name = name.strip()
    
    if not clean_name:
        return JsonResponse({'success': False, 'error': 'Name is empty'}, status=400)
    
    # Use the classmethod we defined earlier
    # Ensure ProductGroup.create(name) handles the DB save properly
    group = ProductGroup.create(clean_name)

    return JsonResponse({
        'success': True,
        'id': group.id,
        'group_key': group.group_key,
        'title': group.group_title
    })
    


@csrf_exempt
def bulk_hold(request, collection_id):  

    collection = Collection.objects.filter(id=collection_id).first()
    print("cid", collection_id)
    try:
        card_ids = request.POST.getlist('card_ids[]')
        if len(card_ids):
            print("lenny", len(card_ids))
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            print("no cards", len(card_ids))
            card_list = list(collection.cards.order_by('id'))
    except json.JSONDecodeError:
        card_list = list(collection.cards.order_by('id'))
    print(card_list)

    for card in card_list:
        perform_status_update(card.active_search_results().id, StatusBase.HELD)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def bulk_status_update(request, status_value):  

    try:
        card_ids = request.POST.getlist('card_ids[]') 
        
        if len(card_ids):    
            print("lenny", len(card_ids))       
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            print("F2")
            card_list = list(collection.cards.order_by('id'))
    except json.JSONDecodeError:
        print("F1")
        card_list = []
        
    for card in card_list:
        perform_status_update(card.active_search_results().id, status_value)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def update_csr_status_only(request, csr_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_status = data.get('status')            
            CardSearchResult.objects.get(id=csr_id).perform_status_update(new_status)
            
            return JsonResponse({
                'success': True, 
                'new_mod_date': ""
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    return JsonResponse({'success': False, 'message': 'Invalid request'})

@csrf_exempt
def price_only(request, csr_id):
    print("reprice", csr_id)

    if not csr_id or csr_id == 'undefined':
        return JsonResponse({'error': 'CSR ID is required'}, status=400)

    lookup.price_only(csr_id, 2)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def text_filter(request):
    all_fields = {}
    csr_ids = []    

    if request.body:
        data = json.loads(request.body)
        if data:
            all_fields = data.get('required_words', {})
            csr_ids = data.get('csr_ids', [])
            new_search = data.get('new_search', False)
    
    csrs = CardSearchResult.objects.filter(id__in=csr_ids)

    if new_search:
        #TODO: ultimately we'll need to separate this from update_fields to filter by something that's not a current value
        for csr in csrs:
            csr.update_fields(all_fields)
            lookup.text_refinement(csr, "", all_fields, Settings.get_default()) 
        csr.save()
    
    return JsonResponse({"success": True, "error": ""})

    
@csrf_exempt
def clear_listed_info(request, card_id):
    
    card = Card.objects.get(id=card_id)
    card.clear_listed_info()
    
    return JsonResponse({"success": True, "error": ""})