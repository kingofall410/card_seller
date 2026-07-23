import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models.Card import Card, Collection
from core.models.Group import ProductGroup
from core.models.TagGroup import TagGroup
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
from django.db.models import OuterRef, Subquery, Count, Prefetch
import traceback
import shlex

def card_status_monitor(request):
    """
    Returns aggregated counts of the LATEST CardSearchResult (CSR) for each card,
    grouped by: Pre-Listing, Priced, Reviewed, Listed, and Sold/Hold.
    """
    # 1. Pull the overall_status value directly from the newest CSR row per card
    latest_status_subquery = CardSearchResult.objects.filter(
        parent_card_id=OuterRef('id')  # Targets the Card ID from the primary query layer
    ).order_by('-id').values('overall_status')[:1]

    # 2. Annotate every card in the database with its singular latest status
    cards_with_latest_status = Card.objects.annotate(
        latest_csr_status=Subquery(latest_status_subquery)
    )

    # 3. Group and count the card objects directly by that single status value
    status_counts = cards_with_latest_status.values('latest_csr_status').annotate(
        total=Count('id')
    ).order_by()
    
    # DEBUG PRINT: View the exact rows coming back from the database group-by clause
    #print("[DEBUG] Raw DB aggregation payload:", list(status_counts))
    
    # Initialize counters
    counts_dict = {
        'pre-listing': 0,
        'priced': 0,
        'reviewed': 0,
        'listed': 0,
        'sold-hold': 0
    }

    # 4. Map the annotated statuses to your workflow groups
    for item in status_counts:
        raw_status = item['latest_csr_status']
        # Fallback to pre-listing if a card has 0 search results recorded yet (None)
        status = raw_status.lower().replace('_', '-').strip() if raw_status else 'pre-listing'
        total = item['total']
        
        if status in [StatusBase.LISTED, StatusBase.CONFIRMED, StatusBase.STAGED]:
            counts_dict['listed'] += total
            
        elif status in [StatusBase.PRICED, StatusBase.AUTO_PRICED, StatusBase.UNLISTED, StatusBase.PENDING]:
            counts_dict['priced'] += total
            
        elif status in [StatusBase.REVIEWED]:
            counts_dict['reviewed'] += total
            
        elif status in [StatusBase.SOLD, StatusBase.HELD]:
            counts_dict['sold-hold'] += total
            
        elif status in [StatusBase.IMPORTED]:
            counts_dict['pre-listing'] += total

    # DEBUG PRINT: View the finalized dictionary map before dispatching response
    #print("[DEBUG] Final mapped counts dict:", counts_dict)

    return JsonResponse({
        'success': True,
        'counts': counts_dict
    })

def build_q_from_filters(filters_json):
    if not filters_json:
        return Q()
    
    data = json.loads(filters_json)
    final_q = Q()
    op_map = {'=': 'exact', '>': 'gt', '>=': 'gte', '<': 'lt', '<=': 'lte'}

    for field, items in data.items():
        field_q = Q()
        
        # Determine the database path for the field
        target = 'latest_status' if field == 'overall_status' else (
            field if hasattr(Card, field) else f"search_results__{field}"
        )

        for f in items:
            op = f.get('op')
            val = f.get('val')
            
            if op == '!=':
                # Use &= for hard exclusion: "Must not be A AND must not be B"
                final_q &= ~Q(**{f"{target}": val})
            else:
                # Use |= for inclusion: "Can be X OR Y"
                lookup = f"{target}__{op_map.get(op, 'exact')}"
                field_q |= Q(**{lookup: val})
        
        # Only combine field_q if it actually contains positive filters
        if field_q:
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
    #card.active_search_results.collapse_token_maps()
    return JsonResponse({"success": 'true'}, status=200)

@csrf_exempt
def rehydrate(request, card_id):
    card = CardArchive.rehydrate({"original_id":card_id}, 117)
    return JsonResponse({"success": 'true'}, status=200)

@csrf_exempt
def re_sku(request, card_id):
    card = Card.objects.get(id=card_id).re_sku()
    return JsonResponse({"success": 'true'}, status=200)

@csrf_exempt
def single_card_test(request, card_id):
    if request.method == 'POST':
        try:
            csr = CardSearchResult.objects.filter(parent_card_id=card_id).last()
            if not hasattr(csr.parent_card, "listed_card_info"):
                ListedInfo.create_from_csr(csr)
            
            for listing_group in csr.listing_groups.all():
                listing_group.save()
            
            #csr.update_value()
            csr.save()
            csr.parent_card.save()
            
            return JsonResponse({"success": 'true'}, status=200)
        except Exception as e:
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)

# Card-related views
@csrf_exempt
def bulk_re_sku(request):
    if request.method == 'POST':
        try:
            card_ids = request.POST.getlist('card_ids[]')
            if len(card_ids):
                print("lenny", len(card_ids))
                card_list = Card.objects.filter(id__in=card_ids).order_by('id')
            else:
                print("no cards", len(card_ids))
                card_list = list(collection.cards.order_by('id'))
        except json.JSONDecodeError:
            return JsonResponse({'error': "no cards"}, status=400)
            
        #print(card_list)

        for card in card_list:
            card.re_sku()
            card.save()
        return JsonResponse({"success": 'true'}, status=200)
            
def do_tags(card, tags):
    for tag in tags:
        tg = TagGroup.create(tag)
        tg.tagged_cards.add(card)
        tg.save()
        card.tags.add(tag)

@csrf_exempt
def update_tags(request, card_id):
    if request.method == "POST":
        # Get the specific taggable object instance
        obj = Card.objects.get(id=card_id)
        raw_tags = request.POST.get("new_tags", "").strip()
        
        if raw_tags:
            # Debug log to verify standard string stream data format
            #logger.debug(f"[TAG UPDATER] Appending string tokens to object ID {pk}: {raw_tags}")
            
            # .add() automatically parses comma separated input strings seamlessly
            tag_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
            obj.tags.add(*tag_list)

            do_tags(obj, tag_list)

    # Redirect back to the inventory viewport layout panel
    return redirect(request.META.get('HTTP_REFERER', '/'))

# Card-related views
@csrf_exempt
def bulk_tag(request):
    
    if request.method == 'POST':
        try:
            card_ids = request.POST.getlist('card_ids[]')
            if len(card_ids):
                print("lenny", len(card_ids))
                card_list = Card.objects.filter(id__in=card_ids).order_by('id')
            else:
                print("no cards", len(card_ids))
                card_list = list(collection.cards.order_by('id'))
        except json.JSONDecodeError:
            return JsonResponse({'error': "no cards"}, status=400)
            
        tag_list = request.POST.getlist("tags[]")
        print(tag_list)
        for card in card_list:
            do_tags(card, tag_list)

        return JsonResponse({"success": 'true'}, status=200)
            

# Card-related views
@csrf_exempt
def card_test(request):
    if request.method == 'POST':
        try:
            card_ids = request.POST.getlist('card_ids[]')
            if len(card_ids):
                print("lenny", len(card_ids))
                card_list = Card.objects.filter(id__in=card_ids).order_by('id')
            else:
                print("no cards", len(card_ids))
                card_list = list(collection.cards.order_by('id'))
        except json.JSONDecodeError:
            return JsonResponse({'error': "no cards"}, status=400)
            
    #print(card_list)

        for card in card_list:
            single_card_test(request, card.id)
            card.save()
        return JsonResponse({"success": 'true'}, status=200)

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

    cc_asr = first_card.active_search_results

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
    #print("CR", card_tuples)
    return render(request, "crop_review.html", {"card_tuples": card_tuples})

@csrf_exempt
def crop(request, card_id):
    # Standard POST retrieval
    
    card = Card.objects.get(id=card_id)
    return render(request, "crop_review.html", {"card_tuples": [(card, card_id), (card, card.reverse_id)]})


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

def card_search_simple_ajax(request):
    search_term = request.GET.get('searchTerm', '').strip()
    timeframe = request.GET.get('timeframe', '30')
    
    # 1. Retrieve 'status' as a list of values (e.g. ['Priced', 'Reviewed'])
    # If no status parameters are passed, or it contains only ['0'], we treat it as unfiltered
    status_list = request.GET.getlist('status')
    collection_id = request.GET.getlist('cid')
    grp_id = request.GET.getlist('grp')
    if '0' in status_list:
        status_list.remove('0')

    
    if collection_id:
        # Start with base queryset
        qs = Card.objects.filter(collection_id=collection_id)
    elif grp_id:
        qs = Card.objects.filter(search_results__listing__ebay_product_group_key=grp_id)
    elif timeframe != '0':
        start_date = timezone.now() - timedelta(days=int(timeframe))
        qs = qs.filter(modification_date__gte=start_date)
    

    # Apply Status Filter (Using list of statuses)
    if status_list:
        qs = qs.filter(search_results__overall_status__in=status_list)

    # 2. Split search term into individual words, respecting quotes
    if search_term:
        try:
            # shlex.split('Topps "Ken Griffey Jr" 1989') -> ['Topps', 'Ken Griffey Jr', '1989']
            parsed_terms = shlex.split(search_term)
        except ValueError:
            # Fallback if quotes are unclosed/invalid (e.g., user is still typing: "Ken Griffey)
            parsed_terms = search_term.split()

        # Build an AND query: every term/phrase must be found in the full name
        search_query = Q()
        for term in parsed_terms:
            if term.strip():
                search_query &= Q(search_results__full_name__icontains=term.strip())
        
        qs = qs.filter(search_query)

    # Call the core logic (limiting to 50 results)
    card_list = collection_views.flatten_collection(qs, limit=50)

    return JsonResponse({
        "draw": int(request.GET.get('draw', 1)),
        "recordsTotal": Card.objects.count(),
        "recordsFiltered": len(card_list), # Simplified for this context
        "data": card_list,
    })

def extract_card_list(request, collection_id=None):
    card_ids = request.POST.getlist('card_ids[]')
    grp_id = request.POST.get('grp_id')
    if len(card_ids):
        print("lenny", len(card_ids))
        return Card.objects.filter(id__in=card_ids).order_by('id'), card_ids
    elif collection_id:
        print("collection", collection_id)
        cards = Card.objects.filter(collection_id=collection_id).order_by('id')
        card_ids = [card.id for card in cards]
        return cards, card_ids
    elif grp_id:
        print("group", grp_id)
        cards = Card.objects.filter(search_results__ebay_product_group__group_key=grp_id).order_by('id')
        card_ids = [card.id for card in cards]
        return cards, card_ids


@csrf_exempt
def get_flat_cards(request, card_id=None):
    cards, card_ids = extract_card_list(request)
    if cards:
        updated_flat_cards = collection_views.flatten_collection(cards)
        return JsonResponse({"success": True, "data":updated_flat_cards})
    else:
        return JsonResponse({"success": True, "data":[]})


@csrf_exempt
def refresh_listing_status(request, card_id=None):
    
    if card_id:
        cards = Card.objects.filter(id=card_id)
        card_ids = [card_id]
        listing_ids = [cards[0].listed_card_info.listing_id]
    else:
        cards, card_ids = extract_card_list(request)
        listing_ids = [card.listed_card_info.listing_id for card in cards if hasattr(card, "listed_card_info")]
    
    core_config = apps.get_app_config("core")
    core_config.queue.schedule_confirm_task(name=f"confirm listings", card=cards[0], callback=lookup.bulk_order_update, params={"card_ids": card_ids, "listing_ids":listing_ids}, on_success_status=StatusBase.CONFIRMED)

    #lookup.bulk_order_update(cards, listing_ids, Settings.get_default())
    #updated_flat_cards = collection_views.flatten_collection(cards)
    return JsonResponse({"success": True})
    
def scope_queryset_to_latest_csr(queryset):
    """
    Isolates the base card query so that ANY downstream joins or filters
    on 'search_results' are restricted to the absolute newest record.
    """
    latest_search_id = CardSearchResult.objects.filter(
        parent_card=OuterRef('pk')
    ).order_by('-id').values('id')[:1]

    # Explicitly filter the baseline relationship to only the latest ID match
    return queryset.filter(search_results__id=Subquery(latest_search_id))

def card_search_ajax(request):
    query = request.GET.get('q', '').strip()
    since_date_str = request.GET.get('timeframe')
    filters_json = request.GET.get('filters')
    is_update = request.GET.get('updates_only') is not None
    
    # Step 1: Isolate the absolute latest CSR record ID row identity
    latest_search_id = CardSearchResult.objects.filter(
        parent_card=OuterRef('pk')
    ).order_by('-id').values('id')[:1]
    
    # Step 2: Tie the baseline query to ONLY see that active row record
    cards_queryset = Card.objects.annotate(
        latest_csr_id=Subquery(latest_search_id)
    ).filter(
        search_results__id=F('latest_csr_id')
    )
    
    # Step 3: Apply text query parameter strictly to the isolated live join path
    if query:
        cards_queryset = cards_queryset.filter(
            Q(search_results__full_name__icontains=query) |
            Q(search_results__year__icontains=query) |
            Q(search_results__brand__icontains=query) |
            Q(search_results__team__icontains=query) 
        )
    
    # Step 4: Extract JSON Sidebar Filters (excluding sort parameters)
    filter_payload = json.loads(filters_json) if filters_json else {}
    filter_only_data = {k: v for k, v in filter_payload.items() if k != 'sort'}
    
    # Build your dynamic Q filters (these will safely execute on the constrained join)
    dynamic_q = build_q_from_filters(json.dumps(filter_only_data))
    cards_queryset = cards_queryset.filter(dynamic_q)
    
    # Step 5: Add modification date constraint if applicable
    if since_date_str:
        target_date = parse_datetime(since_date_str)
        if target_date:
            cards_queryset = cards_queryset.filter(modification_date__gte=target_date)
            
    # Step 6: Handle Sorting execution parameters cleanly
    sort_data = filter_payload.get('sort')
    if sort_data and isinstance(sort_data, list) and len(sort_data) > 0:
        s = sort_data[0]
        field = s.get('val')
        direction = s.get('op', 'asc').lower()
        order_prefix = '-' if direction == 'desc' else ''
        
        if field in ['overall_status', 'status']:
            field = 'search_results__overall_status'
            
        cards_queryset = cards_queryset.order_by(f"{order_prefix}{field}")
    else:
        cards_queryset = cards_queryset.order_by('-id')
    
    cards_list = cards_queryset.distinct()
    
    # Step 7: UI Layer Pagination Processing
    if is_update:
        cards_to_render = cards_list
        has_next = False
        next_page = None
    else:
        paginator = Paginator(cards_list, 10)
        page_num = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_num)
        cards_to_render = page_obj
        has_next = page_obj.has_next()
        next_page = page_obj.next_page_number() if has_next else None

    # Step 8: Render the safe HTML Partial
    html = render_to_string('components/search_results_partial.html', {
        'cards': cards_to_render,
        'is_refresh': is_update
    }, request=request)

    return JsonResponse({
        'html': html,
        'table_data': [], 
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
def delete(request, card_id=None):
    print("delete", request)
    if request.method == 'POST':
        #print("POST")
        card_id = card_id or request.POST.get('card_id')
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
    #print("here", request)
    if request.body and len(request.body) > 0 :
        data = json.loads(request.body)
        csr_id = data["csrId"]
        all_fields = data["allFields"]
        #print(csr_id)
        #print(all_fields)

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
def bulk_update_csr_fields(request):
    if request.method != 'POST':
        return JsonResponse({"error": True, "message": "Invalid request method"}, status=405)
    
    try:
        data = json.loads(request.body)
        # Expecting a list of update objects: [{"csrId": 1, "allFields": {...}}, ...]
        updates = data.get("updates", [])
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"error": True, "message": "Invalid JSON format"}, status=400)

    results = []
    errors = []
    print(updates)
    for item in updates:
        print(item)
        csr_id = item.get("csrId")
        all_fields = item.get("allFields")

        if not csr_id:
            errors.append({"csrId": csr_id, "message": "Missing csrId"})
            continue

        try:
            csr = CardSearchResult.objects.get(id=int(csr_id))
            
            # Apply your existing sanitization logic
            field_data = convert_and_sanitize(all_fields, csr)
            
            if "group_key" in field_data:
                csr.ebay_product_group = None
            
            csr.update_fields(field_data)
            
            # Append the successful update to results
            results.append({
                "csrId": csr_id,
                "updated_data": model_to_dict(csr, fields=CardSearchResult.calculated_fields)
            })
            
        except CardSearchResult.DoesNotExist:
            errors.append({"csrId": csr_id, "message": "Not found"})
        except Exception as e:
            traceback.print_exc()
            errors.append({"csrId": csr_id, "message": str(e)})

    return JsonResponse({
        "success": len(errors) == 0,
        "results": results,
        "errors": errors
    })

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
    li_id = request.POST.get("li_id", None)
    card_id = request.POST.get("card_id", None)
    fieldname = request.POST.get("field")
    fieldvalue = request.POST.get("value")

    if li_id:
        listed_info = ListedInfo.objects.filter(id=int(li_id)).last()
    elif card_id:
        listed_info = ListedInfo.objects.filter(card_id=int(card_id)).last()

    if not listed_info or not fieldname:
        return JsonResponse({"error": True, "message": "Missing parameters"}, status=400)


    # Update the field
    if hasattr(listed_info, fieldname):
        setattr(listed_info, fieldname, fieldvalue)
        listed_info.save()

        if (fieldname=="list_price"):
            card = listed_info.card
            asr = card.active_search_results
            if asr.overall_status == StatusBase.PRICED:
                asr.perform_status_update(StatusBase.REVIEWED)
            card.save()
    else:
        return JsonResponse({"error": True, "message": f"Invalid field '{fieldname}'"}, status=400)

    return JsonResponse({"success": True})

def async_lg_monitor(request):
    since_str = request.GET.get('timeframe')
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
        perform_status_update(card.active_search_results.id, StatusBase.HELD)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def bulk_status_update(request, status_value):  

    try:
        card_ids = request.POST.getlist('card_ids[]') 
        force_price = request.POST.get('force_price') 
        
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
        card.active_search_results.perform_status_update(status_value, force_price)

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