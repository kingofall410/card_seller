# Collection-related views
from django.views.decorators.csrf import csrf_exempt
import os
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.conf import settings as app_settings
from django.core.files.storage import default_storage
from django.utils.timezone import now
from services import lookup, ebay
from services.models.models import Settings
from core.models.Card import Card, Collection
from services.models.task import ListingTask, ConfirmTask
from core.models.CardSearchResult import CardSearchResult
from core.views import card_views, image_views
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, F
from django.forms.models import model_to_dict
from django.apps import apps
from django.db.models import Prefetch
from core.models.Status import StatusBase
from core.models.TagGroup import TagGroup
from django.views.decorators.http import require_POST
from django.db.models import Case, When, Value, CharField, OuterRef, Subquery, FloatField
from django.db.models.functions import Concat, Coalesce, Greatest, Cast, Ceil
from pathlib import Path
from datetime import timedelta, datetime
from django.utils import timezone
from itertools import chain
from core.models.ProductGroup import ProductGroup
from core.models.ListedInfo import ListedInfo
from core.models.ListingStatus import ListingStatus

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



    lgs = list(chain.from_iterable(card.active_search_results.get_pricing_groups for card in card_list))
    lgids = [lg.id for lg in lgs]


    core_config = apps.get_app_config("core")
    core_config.queue.schedule_pricing_task(name=f"refresh lgs", csr=card_list[0].active_search_results, card=card_list[0], callback=lookup.refresh_listing_groups, params={"lg_ids":lgids}, on_success_status=StatusBase.PRICED)
    
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

def flatten_collection(base_queryset, limit=None, status_list=None, excl_status_list=None, query_string=None):
    """
    Flattens card data by driving the query from the CardSearchResult table.
    Uses unique annotation names to avoid conflicting with model fields.
    """
    from django.db.models import Subquery, OuterRef, F, Q, Case, When, Value, CharField, FloatField
    from django.db.models.functions import Coalesce, Cast, Ceil, Greatest
    from pathlib import Path

    # 1. Start with search results linked to the incoming card scope
    query = CardSearchResult.objects.filter(parent_card__in=base_queryset)

    # 2. Isolate to the absolute newest CSR row per card
    latest_id_subquery = CardSearchResult.objects.filter(
        parent_card=OuterRef('parent_card')
    ).order_by('-id').values('id')[:1]
    
    query = query.filter(id=Subquery(latest_id_subquery))

    # 3. Apply workflow status constraints
    if status_list:
        query = query.filter(overall_status__in=status_list)

    if excl_status_list:    
        query = query.exclude(overall_status__in=excl_status_list)
        
    # 4. Apply text search filters
    if query_string:
        query = query.filter(
            Q(full_name__icontains=query_string) |
            Q(year__icontains=query_string) |
            Q(brand__icontains=query_string) |
            Q(team__icontains=query_string)
        )

    # Isolated Subquery to get the latest task date without causing N+1 hits
    latest_task_scheduled_subquery = ListingTask.objects.filter(
        card=OuterRef('parent_card')
    ).order_by('-scheduled_for').values('scheduled_for')[:1]


    # Isolated Subquery to get the latest task date without causing N+1 hits
    latest_confirmtask_scheduled_subquery = ConfirmTask.objects.filter(
        card=OuterRef('parent_card')
    ).order_by('-created_at').values('created_at')[:1]

    # Isolated Subquery to get the latest task date without causing N+1 hits
    latest_listingstatus_subquery = ListingStatus.objects.filter(
        listing_info=OuterRef('parent_card__listed_card_info')
    ).order_by('-create_date').values('create_date')[:1]

    # Isolated Subquery to get the primary tag group without causing N+1 hits
    ptg_scheduled_subquery = TagGroup.objects.filter(
        tagged_cards=OuterRef('parent_card')
    ).order_by('-id').values('group_title')[:1]

    # 5. Extract parent fields using unique names to prevent model conflicts
    query = query.annotate(
        fetched_card_id=F('parent_card__id'),
        fetched_collection_id=F('parent_card__collection_id'),
        fetched_value=F('parent_card__value'),
        fetched_mod_date=F('parent_card__modification_date'),
        fetched_sku=F('parent_card__listed_card_info__sku'),
        fetched_msrp=F('parent_card__listed_card_info__msrp'),
        fetched_list_price=F('parent_card__listed_card_info__list_price'),
        fetched_qty=F('parent_card__listed_card_info__list_qty'),
        
        # Injected listing task timestamp annotation
        latest_task_scheduled=Subquery(latest_task_scheduled_subquery),
        latest_confirmtask_scheduled=Subquery(latest_confirmtask_scheduled_subquery),
        latest_listingstatus=Subquery(latest_listingstatus_subquery),
        primary_tag_group=Subquery(ptg_scheduled_subquery),
        
        # Local CSR Field Overrides
        custom_year=Case(
            When(year_is_manual=True, then=F('year_m')),
            default=F('year'),
            output_field=CharField()
        ),
        custom_brand=Case(
            When(brand_is_manual=True, then=F('brand_m')),
            default=F('brand'),
            output_field=CharField()
        ),
        custom_name=Case(
            When(full_name_is_manual=True, then=F('full_name_m')),
            default=F('full_name'),
            output_field=CharField()
        ),
        custom_subset=Coalesce(
            Case(
                When(subset_is_manual=True, then=F('subset_m')),
                default=F('subset'),
                output_field=CharField()
            ),
            Value('')
        ),
        custom_city=Case(
            When(city_is_manual=True, then=F('city_m')),
            default=F('city'),
            output_field=CharField()
        ),
        custom_team=Case(
            When(team_is_manual=True, then=F('team_m')),
            default=F('team'),
            output_field=CharField()
        ),
        custom_card_name=Case(
            When(card_name_is_manual=True, then=F('card_name_m')),
            default=F('card_name'),
            output_field=CharField()
        ),
        custom_card_nr=Case(
            When(card_number_is_manual=True, then=F('card_number_m')),
            default=F('card_number'),
            output_field=CharField()
        ),
        custom_parallel=Case(
            When(parallel_is_manual=True, then=F('parallel_m')),
            default=F('parallel'),
            output_field=CharField()
        ),
        custom_title=Case(
            When(parallel_is_manual=True, then=F('title_to_be_m')),
            default=F('title_to_be'),
            output_field=CharField()
        ),
        
        # Numeric Baseline Realignment
        min_offer_val=Coalesce(F("min_offer"), Value(0.0), output_field=FloatField()),
        max_offer_val=Coalesce(F("max_offer"), Value(0.0), output_field=FloatField()),
        min_avg_val=Coalesce(F("min_avg"), Value(0.0), output_field=FloatField()),
        max_avg_val=Coalesce(F("max_avg"), Value(0.0), output_field=FloatField()),
        
        highest_raw_val=Greatest(
            Coalesce(Cast(F('max_offer'), FloatField()), Value(0.0)), 
            Coalesce(Cast(F('max_avg'), FloatField()), Value(0.0))
        ),
        
        # Map straight projections from existing CSR model fields
        legacy_sku=F('sku'),
        csr_id=F('id'),
        legacy_msrp=F('ebay_msrp'),
        product_group_name=F('ebay_product_group__group_title'),
        product_group_key=F('ebay_product_group__group_key'),
        
        val_range_str=Case(
            When(parent_card__value=0, then=Value('$0.00')),
            When(parent_card__value__lt=1, then=Value('$0.00 - $0.99')),
            When(parent_card__value__lt=3, then=Value('$1.00 - $2.99')),
            When(parent_card__value__lt=5, then=Value('$3.00 - $4.99')),
            default=Value('$10+'),
            output_field=CharField(),
        )
    )

    # 6. Apply trailing calculations and select values using the clean aliases
    query = query.annotate(
        scale_max_val=Ceil(F('highest_raw_val') / 5.0) * 5.0
    ).values(
        'fetched_card_id', 'fetched_collection_id', 'fetched_value', 'fetched_mod_date', 
        'fetched_sku', 'fetched_msrp', 'fetched_qty', 'fetched_list_price',
        'custom_year', 'custom_brand', 'custom_subset', 'custom_city', 'custom_team', 
        'custom_name', 'custom_card_name', 'custom_card_nr', 'custom_parallel', 'custom_title',
        'overall_status', 'legacy_sku', 'csr_id', 'legacy_msrp', 'min_offer_val', 'max_offer_val', 'min_avg_val', 
        'max_avg_val', 'scale_max_val', 'product_group_name', 'product_group_key', 'val_range_str',
        'latest_task_scheduled', 'latest_confirmtask_scheduled', 'latest_listingstatus', 'primary_tag_group'  # Passed through raw row generation
    ).order_by('-fetched_card_id')
    
    if limit:
        raw_rows = list(query[:limit])
    else:
        raw_rows = list(query)

    cards_list = []

    safe_min_dt = timezone.make_aware(datetime(1970, 1, 1))

    for row in raw_rows:
        # Build the natural sort components manually from the dictionary data
        
        
        title_parts = [
            row['custom_year'],
            row['custom_brand'],
            row['custom_subset'] if (row['custom_subset'] and row['custom_subset'].strip()) else None,
            row['custom_card_name'] if (row['custom_card_name'] and row['custom_card_name'].strip()) else None,
            row['custom_card_nr'] if (row['custom_card_nr'] and row['custom_card_nr'].strip()) else None,
            row['custom_parallel'] if (row['custom_parallel'] and row['custom_parallel'].strip()) else None,
        ]
        
        # Clean out empty strings and extra spaces exactly like your property does
        natural_sort_title = " ".join(str(part).strip() for part in title_parts if part and str(part).strip())

        price_sort_val = row['fetched_list_price'] if row['fetched_list_price'] and row['fetched_list_price'] > 0 else row['fetched_msrp'] if row['fetched_msrp'] else 0
        
        cards_list.append({
            'id': row['fetched_card_id'],
            'collection_id': row['fetched_collection_id'],
            'value': row['fetched_value'],
            'modification_date': row['fetched_mod_date'],
            'sku': row['fetched_sku'],
            'msrp': row['fetched_msrp'],
            'legacy_msrp': row['legacy_msrp'],
            'list_price': row['fetched_list_price'],
            'qty': row['fetched_qty'],
            'year': row['custom_year'],
            'brand': row['custom_brand'],
            'subset': row['custom_subset'],
            'city': row['custom_city'],
            'team': row['custom_team'],
            'name': row['custom_name'],
            'card_name': row['custom_card_name'],
            'parallel': row['custom_parallel'],
            'title_to_be': row['custom_title'],
            'card_nr': row['custom_card_nr'],
            'overall_status': row['overall_status'],
            'legacy_sku': row['legacy_sku'],
            'csr_id': row['csr_id'],
            'min_offer': row['min_offer_val'],
            'max_offer': row['max_offer_val'],
            'min_avg': row['min_avg_val'],
            'max_avg': row['max_avg_val'],
            'scale_max': row['scale_max_val'],
            'product_group_name': row['product_group_name'],
            'product_group_key': row['product_group_key'],
            'val_range': row['val_range_str'],
            'latest_task_scheduled': max((row['latest_confirmtask_scheduled'] or safe_min_dt), (row['latest_task_scheduled'] or safe_min_dt), (row['latest_listingstatus'] or safe_min_dt)),
            'primary_tag_group': row['primary_tag_group'],
            'natural_sort': natural_sort_title,
            'all_price_sort': price_sort_val
        })

    # 8. Batch Map Images using the translated parent card IDs
    card_ids = [card_dict['id'] for card_dict in cards_list]
    image_map = {
        c.id: c for c in Card.objects.filter(
            id__in=card_ids
        ).select_related('cropped_image', 'cropped_reverse')
    }
    
    for card_data in cards_list:
        card_obj = image_map.get(card_data['id'])
        card_data['front_thumb_url'] = None
        card_data['reverse_thumb_url'] = None
        card_data['front_url'] = None
        card_data['reverse_url'] = None

        if card_obj:
            if card_obj.cropped_image and card_obj.cropped_image.img:
                if Path(card_obj.cropped_image.img.path).exists():
                    card_data['front_url'] = card_obj.cropped_image.url()
                    card_data['front_thumb_url'] = card_obj.cropped_image.thumbnail.url
            
            if card_obj.cropped_reverse and card_obj.cropped_reverse.img:
                if Path(card_obj.cropped_reverse.img.path).exists():
                    card_data['reverse_url'] = card_obj.cropped_reverse.url()
                    card_data['reverse_thumb_url'] = card_obj.cropped_reverse.thumbnail.url

    return cards_list

def view_collection(request, collection_id):
        
    text_query = request.GET.get('q')
    csr_ids = request.GET.get('csr_ids', None)
    status_list = request.GET.getlist('status')
    exclude_status_list = request.GET.getlist('exclude_status')
    collection_id_list = request.GET.getlist('cid')
    grp_id_list = request.GET.getlist('grp_id')
    timeframe = request.GET.get('timeframe', '0')
    start_listing_date = request.GET.get('start_listing_date', None)
    end_listing_date = request.GET.get('end_listing_date', None)

    if csr_ids:
        csr_id_list = csr_ids.split(",")
        query_set = Card.objects.filter(search_results__id__in=csr_id_list)
    else:
        query_set = Card.objects.all()

    if grp_id_list:
        query_set = query_set.filter(search_results__ebay_product_group__group_key__in=grp_id)
        

    if collection_id_list:
        query_set = query_set.filter(collection_id__in=collection_id_list)

    if start_listing_date and end_listing_date:
        start_date = timezone.make_aware(datetime.fromisoformat(start_listing_date))
        end_date = timezone.make_aware(datetime.fromisoformat(end_listing_date))
        query_set = query_set.filter(
            listed_card_info__listing_datetime__date__gte=start_date
        ).filter(listed_card_info__listing_datetime__date__lte=end_date)
    else:
        start_date = timezone.now() - timedelta(days=int(timeframe))
        query_set = query_set.filter(modification_date__gte=start_date)   
    

    # Step 2: Pass filters down to be safely evaluated against ONLY the latest CSR
    card_list = flatten_collection(
        base_queryset=query_set, 
        status_list=status_list,
        excl_status_list=exclude_status_list,
        query_string=text_query
    )

    # Step 3: Sort the clean dictionary payload safely
    card_list = sorted(
        card_list, 
        key=lambda x: x['product_group_key'] if x['product_group_key'] else ''
    )
    
    return render(request, "collection_builder.html", {
        "cards": card_list, 
        "q": text_query, 
        "timeframe": timeframe, 
        "settings": Settings.get_default(), 
        "StatusBase": StatusBase
    })

def product_group_detail(request, pk):

    product_group = get_object_or_404(ProductGroup, group_key=pk)
    query_set = Card.objects.filter(search_results__ebay_product_group__group_key=pk)
    # Step 2: Pass filters down to be safely evaluated against ONLY the latest CSR
    card_list = flatten_collection(
        base_queryset=query_set
    )

    # Step 3: Sort the clean dictionary payload safely
    card_list = sorted(
        card_list, 
        key=lambda x: x['product_group_key'] if x['product_group_key'] else ''
    )
    product_group.save()
    for card in query_set:
        card.listed_card_info.save()
    return render(request, "group_view.html", {
        "cards": card_list, 
        "q": "", 
        "timeframe": "7", 
        "settings": Settings.get_default(), 
        "StatusBase": StatusBase,
        "group": product_group
    })

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

'''def product_group_detail(request, pk):
    product_group = get_object_or_404(ProductGroup, group_key=pk)

    if request.method == "POST":
        product_group.group_title = request.POST.get("group_title")
        product_group.group_key = request.POST.get("group_key")
        product_group.group_image_link = request.POST.get("group_image_link") or None
        
        replaced_by_id = request.POST.get("replaced_by")
        product_group.replaced_by_id = replaced_by_id if replaced_by_id else None
        
        # Calling save triggers _calculate_summary_attribs() as defined in your model
        product_group.save() 
        return redirect("edit_product_group", pk=pk)

    context = {
        "product_group": product_group,
        "all_product_groups": ProductGroup.objects.exclude(pk=pk).only("id", "group_title", "group_key"),
    }
    return render(request, "product_groups.html", context)'''

def listings_list(request, timeframe=7):
    
    # Safely parse timeframe query parameter
    try:
        timeframe_days = int(request.GET.get('timeframe', timeframe))
    except (ValueError, TypeError):
        timeframe_days = 7

    end_date = timezone.now()
    start_date = end_date - timedelta(days=timeframe_days)

    # 1. ProductGroup: Prevent duplicate groups & prefetch related models
    groups = (
        ProductGroup.objects.filter(
            products__parent_card__listed_card_info__listing_datetime__range=(start_date, end_date)
        )
        .distinct()
    )

    # 2. Standalone Items: Optimize range query & prefetch foreign keys
    standalone_items = (
        ListedInfo.objects.filter(
            product_group__isnull=True,
            listing_datetime__range=(start_date, end_date)  # Replaces gte/lte/isnull combo
        )
        .select_related('product_group')  # Pre-loads foreign keys to avoid N+1 queries in template
        .prefetch_related('listing_statuses')
        .order_by('-listing_datetime')
    )

    context = {
        'groups': groups,
        'standalone_items': standalone_items,
        'timeframe': timeframe_days
    }
    
    #lid_list = [g.listing_id for g in groups]+[i.listing_id for i in standalone_items]
    #ebay.bulk_order_update(lid_list, Settings.get_default())
    return render(request, 'listing_list.html', context)
