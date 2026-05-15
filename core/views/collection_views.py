# Collection-related views
from django.views.decorators.csrf import csrf_exempt
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
from services import lookup
from core.models.CardSearchResult import CardSearchResult
from core.views import card_views, image_views
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, F
from django.forms.models import model_to_dict
from django.apps import apps
from django.db.models import Prefetch
from core.models.Status import StatusBase
from django.views.decorators.http import require_POST
from django.db.models import Case, When, Value, CharField, OuterRef, Subquery, FloatField
from django.db.models.functions import Concat, Coalesce, Greatest, Cast, Ceil
from pathlib import Path
from datetime import timedelta
from django.utils import timezone

@require_POST
@csrf_exempt
def price_collection(request, collection_id):  

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

    core_config = apps.get_app_config("core")
    for card in card_list:
        core_config.queue.schedule_pricing_task(name=f"price card {card.id}", csr=card.active_search_results, card=card, callback=lookup.price_only_card, params={"card_id": card.id, "settings_id":2}, on_success_status=StatusBase.PRICED)

    return JsonResponse({"success": True, "error": ""})

@require_POST # Ensure only POST requests hit this
@csrf_exempt
def identify_collection(request, collection_id):
    print("cid", collection_id)

    collection = Collection.objects.get(id=collection_id)
    try:
        card_ids = request.POST.getlist('card_ids[]') 
        
        if len(card_ids):           
            card_list = Card.objects.filter(id__in=card_ids).order_by('id')
        else:
            card_list = list(collection.cards.order_by('id'))
    except json.JSONDecodeError:
        card_list = list(collection.cards.order_by('id'))
    
    print(card_list)
    
    core_config = apps.get_app_config("core")
    for card in card_list:
        core_config.queue.schedule_id_task(name=f"ID card {card.id}", callback=image_views.perform_id, params={"card_id":card.id}, card=card)

    return JsonResponse({"success": True, "error": ""})

@csrf_exempt
def update_collection(request):
    collection_id = request.POST.get("collectionId")
    field_name = request.POST.get("field")
    field_value = request.POST.get("value")

    # 1. Fetch collection safely
    try:
        collection = Collection.objects.get(id=collection_id)
    except Collection.DoesNotExist:
        return JsonResponse({"error": True, "message": "Collection not found"}, status=404)

    # 2. Ensure the field exists on the model
    if field_name not in [f.name for f in Collection._meta.get_fields()]:
        return JsonResponse({"error": True, "message": f"Invalid field '{field_name}'"}, status=400)

    # 3. Convert field_value to the correct Python type
    field = Collection._meta.get_field(field_name)
    try:
        python_value = field.to_python(field_value)
    except Exception as e:
        return JsonResponse({"error": True, "message": f"Invalid value: {e}"}, status=400)

    # 4. Assign and save
    setattr(collection, field_name, python_value)
    collection.save(update_fields=[field_name])

    return JsonResponse({
        "success": True,
        "message": "Collection updated successfully",
        "collection": model_to_dict(collection, fields=[field_name])
    })


@csrf_exempt
def export_collection(request, collection_id):
    print("export collection")
    settings = Settings.objects.first()

    if not collection_id or collection_id == 'undefined':
        return JsonResponse({'error': 'Collection ID is required'}, status=400)
    
    collection = Collection.objects.get(id=collection_id)
    csrs = collection.get_default_exports()

    return export_handler.export_zip(csrs)
from django.db.models import Count, Sum, Q

def manage_collection(request):
    # This single query calculates all stats for every collection at once
    collections = Collection.objects.annotate(
        total_cards=Count('cards'),
        num_listed=Count('cards', filter=Q(cards__search_results__overall_status=StatusBase.LISTED)),
        num_pending=Count('cards', filter=Q(cards__search_results__overall_status=StatusBase.PENDING)),
        num_failed=Count('cards', filter=Q(cards__search_results__overall_status=StatusBase.FAILED))
    )
    
    columns = ['id', 'name', 'completion_pct', 'weighted_completion_pct', 'total_cards', 'todos', 'num_failed', 'total_value', 'num_listed', 'num_pending']
    rows = []

    for c in collections:
        rows.append({
            'id': c.id,
            'name': c.name,
            'total_cards': c.total_cards,
            'todos': c.total_cards-(c.num_listed+c.num_pending), 
            'completion_pct': (c.num_listed+c.num_pending+c.num_failed)/c.total_cards if (c.total_cards > 0) else 0,
            'weighted_completion_pct': c.num_listed+c.num_pending+c.num_failed, 
            'todos': c.total_cards-(c.num_listed+c.num_pending), 
            'num_failed': c.num_failed,
            'num_listed': c.num_listed,
            'num_pending': c.num_pending,
            'total_value': c.value or 0
        })
    return render(request, "collection_management.html", {
        "columns": columns,
        "rows": rows
    })

def spreadsheet_rows_from_search_result(cards, field_names):
    rows = []
    print("sr", cards, field_names)
    for card in cards:
        asr = card.active_search_results
        row = {}
        if asr:
            for field in field_names:
                display_attr = f'display_{field}'
                if hasattr(asr, display_attr):
                    value = getattr(asr, display_attr)
                    row[field] = value if value is not None else ''
                elif field=="card_id":
                    row[field] = card.id
            row["front"] = card.cropped_image.url() if card.cropped_image else ""
            row["reverse"] = card.cropped_reverse.url() if card.cropped_reverse else ""
            row["collection_id"] = card.collection_id
            row["status"] = asr.overall_status
            #row["card_id"] = card.id
            rows.append(row)
    return rows

#view single collections
#TODO: should do this based on specific next_collection calls, pagniator is just messy
#TODO: fuck the paginator for now


def new_collection(request):
    collection = Collection.objects.create()
    return redirect('collection', collection.id)
def flatten_collection(base_queryset, limit=None):
    # 1. Subquery for latest result
    latest_search_id = CardSearchResult.objects.filter(
        parent_card=OuterRef('pk')
    ).order_by('-id').values('id')[:1]

    # 2. Base Filter & Relationship Join Annotations
    query = base_queryset.filter(
        search_results__id=Subquery(latest_search_id)
    ).distinct().order_by('-id').annotate(
        # Year Override Logic
        year=Case(
            When(search_results__year_is_manual=True, then=F('search_results__year_m')),
            default=F('search_results__year'),
            output_field=CharField()
        ),

        # Brand Override Logic
        brand=Case(
            When(search_results__brand_is_manual=True, then=F('search_results__brand_m')),
            default=F('search_results__brand'),
            output_field=CharField()
        ),

        # Name Override Logic
        name=Case(
            When(search_results__full_name_is_manual=True, then=F('search_results__full_name_m')),
            default=F('search_results__full_name'),
            output_field=CharField()
        ),

        # Subset Override Logic
        subset=Coalesce(
            Case(
                When(search_results__subset_is_manual=True, then=F('search_results__subset_m')),
                default=F('search_results__subset'),
                output_field=CharField()
            ),
            Value('')
        ),

        # City Override Logic
        city=Case(
            When(search_results__city_is_manual=True, then=F('search_results__city_m')),
            default=F('search_results__city'),
            output_field=CharField()
        ),

        # Team Override Logic
        team=Case(
            When(search_results__team_is_manual=True, then=F('search_results__team_m')),
            default=F('search_results__team'),
            output_field=CharField()
        ),

        # 🛠️ FIX 1: Explicitly resolve the backend fields properly via relation spans
        min_offer=Coalesce(
            "search_results__min_offer", 
            0.0, 
            output_field=FloatField()
        ),
        max_offer=Coalesce(
            "search_results__max_offer", 
            0.0, 
            output_field=FloatField()
        ),
        min_avg=Coalesce(
            "search_results__min_avg",
            0.0,
            output_field=FloatField()
        ),
        max_avg=Coalesce(
            "search_results__max_avg",
            0.0,
            output_field=FloatField()
        ),

        # 🛠️ FIX 2: Explicit relation paths + Null safety wrap 
        highest_raw_val=Greatest(
            Coalesce(Cast('search_results__max_offer', FloatField()), 0.0), 
            Coalesce(Cast('search_results__max_avg', FloatField()), 0.0)
        ),
        
        # Static allocations
        overall_status=F('search_results__overall_status'),
        legacy_sku=F('search_results__sku'),
        csr_id=F('search_results__id'),
        product_group_name=F('search_results__ebay_product_group__group_title'),
        product_group_key=F('search_results__ebay_product_group__group_key'),
        val_range=Case(
            When(value=0, then=Value('$0.00')),
            When(value__lt=1, then=Value('$0.00 - $0.99')),
            When(value__lt=3, then=Value('$1.00 - $2.99')),
            When(value__lt=5, then=Value('$3.00 - $4.99')),
            default=Value('$10+'),
            output_field=CharField(),
        ),
        sku=F('listed_card_info__sku')
    )

    # 🛠️ FIX 3: Chain-annotate 'scale_max' so it can reference 'highest_raw_val'
    query = query.annotate(
        scale_max=Ceil(F('highest_raw_val') / 5.0) * 5.0
    ).values(
        'id', 'collection_id', 'value', 'year', 'brand', 'subset', 'city', 'overall_status', 
        'team', 'name', 'val_range', 'sku', 'legacy_sku', 'csr_id', 'min_offer', 'max_offer', 
        'min_avg', 'max_avg', 'scale_max', 'product_group_name', 'product_group_key', 'modification_date'
    )

    # 3. Limit / Slicing executions
    if limit:
        cards_list = list(query[:limit])
    else:
        cards_list = list(query)

    # Extract IDs for Image processing
    card_ids = [card_dict['id'] for card_dict in cards_list]

    # Batch process image verification mapping 
    image_map = {
        c.id: c for c in Card.objects.filter(
            id__in=card_ids
        ).select_related('cropped_image', 'cropped_reverse')
    }
    
    for card_data in cards_list:
        card_obj = image_map.get(card_data['id'])
        card_data['front_url'] = None
        card_data['reverse_url'] = None

        if card_obj:
            if card_obj.cropped_image and card_obj.cropped_image.img:
                if Path(card_obj.cropped_image.img.path).exists():
                    card_data['front_url'] = card_obj.cropped_image.thumbnail.url
            
            if card_obj.cropped_reverse and card_obj.cropped_reverse.img:
                if Path(card_obj.cropped_reverse.img.path).exists():
                    card_data['reverse_url'] = card_obj.cropped_reverse.thumbnail.url

    return cards_list
    
def view_collection(request, collection_id):
    
    if collection_id == 0:
        return view_ad_hoc_collection(request)
    
    query = request.GET.get('q')
    status_list = request.GET.getlist('status')
    collection_id = request.GET.get('cid')
    grp_id = request.GET.get('group_key')    
    timeframe = request.GET.get('timeframe', '0')

    if '0' in status_list:
        status_list.remove('0')
    
    if collection_id:
        # Start with base queryset
        qs = Card.objects.filter(collection_id=collection_id)
    elif grp_id:
        qs = Card.objects.filter(
            search_results__ebay_product_group__group_key=grp_id
        ).prefetch_related(
            'search_results',
            'search_results__ebay_product_group' # Prefetches the product group relation
        ).distinct()
    elif timeframe != '0':
        start_date = timezone.now() - timedelta(days=int(timeframe))
        qs = Card.objects.filter(modification_date__gte=start_date)        
    else:
        qs = Card.objects.all()
        timeframe=120

    # Apply Status Filter (Using list of statuses)
    if status_list:
        qs = qs.filter(search_results__overall_status__in=status_list)
        
    if not query and not timeframe:
        return render(request, "collection_builder.html", {"settings":Settings.get_default(), "StatusBase":StatusBase})    
    
    # 3. Apply Global Text Search
    if query:
        contains_filters = Q(
            Q(search_results__full_name__icontains=query) |
            Q(search_results__year__icontains=query) |
            Q(search_results__brand__icontains=query) |
            Q(search_results__overall_status__icontains=query) |
            Q(search_results__team__icontains=query) 
        )

        # Filter against the SearchResult model linked to the Card
        qs = qs.filter(contains_filters)
    

    # 5. Use your core logic to get the final list (annotations, images, etc.)
    # We pass the filtered queryset 'qs' here
    card_list = flatten_collection(qs)
    return render(request, "collection_builder.html", {"cards":card_list, "q":query, "since":timeframe, "settings":Settings.get_default(), "StatusBase":StatusBase})
    #return render(request, "ad_hoc_collection.html", {"cards":Card.objects.all(), "settings":settings, "StatusBase":StatusBase})

def view_ad_hoc_collection(request, card_ids=None):
    cards = []
    if card_ids:
        cards = Card.objects.prefetch_related(
            'search_results',
            'listed_card_info',
            'listing_tasks'
        ).filter(id__in=card_ids)

    settings = Settings.get_default()
    columns = []
    rows = []
    columns = CardSearchResult.listing_fields
    #rows = spreadsheet_rows_from_search_result(collection.cards.all(), columns)
    #cards = Card.objects.filter(collection_id=173)
    #return render(request, "components/search_panes.html", {"cards":cards})
    return render(request, "ad_hoc_collection.html", {"cards":Card.objects.all(), "settings":settings, "columns":columns, "rows":rows, "StatusBase":StatusBase})
    
def listing_view(request):
    columns = CardSearchResult.listing_fields

    cards = Card.objects.filter(
        Q(search_results__ebay_listing_id__isnull=False) & ~Q(search_results__ebay_listing_id='') |
        Q(search_results__sku__isnull=False) & ~Q(search_results__sku='') |
        Q(search_results__ebay_offer_id__isnull=False) & ~Q(search_results__ebay_offer_id='') & ~Q(search_results__ebay_offer_id='None' )|
        Q(search_results__ebay_listing_datetime__isnull=False)
    ).distinct()
    rows = spreadsheet_rows_from_search_result(cards, columns)
        
    return render(request, "spreadsheet_only.html", {"columns":columns, "rows":rows})

def set_default_collection(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)
    Collection.objects.update(is_default=False)

    # Set the one with matching ID to True
    Collection.objects.filter(id=collection_id).update(is_default=True)

@csrf_exempt
def move_card_to_collection(card_or_id, collection_or_id):
    if not isinstance(collection_or_id, Collection):
        collection_or_id = get_object_or_404(Collection, id=collection_or_id)

    if not isinstance(card_or_id, Card):
        card_or_id = get_object_or_404(Card, id=card_or_id)
    
    card_or_id.collection = collection_or_id
    card_or_id.save()

def card_search_spreadsheet_view(request):
    columns = CardSearchResult.listing_fields
    query = request.GET.get('q', '').strip()
    
    # Base Queryset: Start with all cards or a filtered subset
    cards = Card.objects.all()

    if query:
        # Generic search across common fields
        cards = cards.filter(
            Q(name__icontains=query) |
            Q(search_results__ebay_listing_id__icontains=query) |
            Q(search_results__sku__icontains=query) |
            Q(search_results__ebay_offer_id__icontains=query)
        ).distinct()
    else:
        # Optional: Limit results if no search is performed to prevent crashing the browser
        cards = cards.none() 

    rows = spreadsheet_rows_from_search_result(cards, columns)

    # If the request is AJAX, return JSON for Handsontable to consume
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({"data": rows})

    return render(request, "spreadsheet_search.html", {
        "columns": columns, 
        "rows": rows,
        "query": query
    })

@csrf_exempt
def move_to_collection3(request, collection_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            card_ids = data.get('card_ids', [])
            target_collection = Collection.objects.get(id=collection_id)

            if not card_ids:
                return JsonResponse({'ok': False, 'message': 'No cards specified'}, status=400)

            # Bulk update the collection_id for all selected cards
            Card.objects.filter(id__in=card_ids).update(collection=target_collection)

            return JsonResponse({
                'ok': True, 
                'message': f'Moved {len(card_ids)} cards successfully.'
            })

        except Exception as e:
            return JsonResponse({'ok': False, 'message': str(e)}, status=500)
            
    return JsonResponse({'ok': False, 'message': 'Invalid method'}, status=405)