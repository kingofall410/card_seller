from django import template
import json
from core.models.CardSearchResult import CardSearchResult, ProductGroup
from core.models.Card import Collection
from core.models.Status import StatusBase
from services.models import Brand, KnownName, Team, City, CardAttribute, Subset, Condition, Parallel
from django.db.models import F

register = template.Library()

@register.filter
def get_attribute(obj, attr):
    retval = getattr(obj, attr, None)
    return retval or ""

@register.filter
def crop_display_img(obj):
    return obj.crop_display_img()

@register.filter
def str_replace(value, arg):
    """Usage: {{ value|str_replace:"old,new" }}"""
    old, new = arg.split(',')
    return value.replace(old, new)

@register.filter
def should_display(obj, field_name):
    displays = getattr(obj, "display_fields", [])
    if field_name not in displays:
        return False

    try:
        is_manual = getattr(obj, f"{field_name}_is_manual", False)
        manual_val = getattr(obj, f"{field_name}_m", None)
        base_val = getattr(obj, field_name, None)
        return (is_manual and manual_val not in [None, '', {}]) or (not is_manual and base_val not in [None, '', {}])
    except AttributeError:
        return False
    
@register.filter
def get_field_verbose(obj, field_name):
    try:
        return obj._meta.get_field(field_name).verbose_name.title()
    except Exception:
        return field_name.replace("_", " ").title()
    
@register.filter
def dict_get(d, key):
    try:
        options = d.get(key, False)
        return options
    except (TypeError, AttributeError):
        return None

@register.filter
def get_portrait(card, id):
    return card.get_portrait(id)

@register.filter
def get_crop_params(card, id):
    return card.get_crop_params(id)

@register.filter
def get_cropped(card, id):
    return card.get_cropped(id)

@register.simple_tag
def get_collections():
    return Collection.objects.order_by('-id')

@register.simple_tag
def get_calculated():
    return CardSearchResult.calculated_fields

@register.simple_tag
def get_status_icon(ca):
    return Collection.objects.order_by('-id')


@register.simple_tag
def get_overrideables():
    return CardSearchResult.overrideable_fields

@register.simple_tag
def get_display():
    return CardSearchResult.display_fields

@register.simple_tag
def get_checkboxes():
    return CardSearchResult.checkbox_fields

@register.filter
def status_icon_meta(value):
    return StatusBase.get_meta(value)

@register.simple_tag
def get_textonly():
    return CardSearchResult.text_fields

@register.simple_tag
def get_product_groups():
    return [{"id": pg.id, "name": pg.name} for pg in ProductGroup.objects.all()]

@register.simple_tag
def get_all_options(field_key, csrId=None, collection_id=None):

    #print("key", field_key, ',', csrId, ',', collection_id)
    if collection_id:
        #if no specific CSR Is passed, we just return everything
        try:
            if field_key == "brands" or field_key == CardSearchResult.stupid_map("brands"):
                used_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('brand', flat=True)
                return Brand.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "subsets" or field_key == CardSearchResult.stupid_map("subsets"):
                used_subset_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('subset', flat=True)
                return Subset.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "names" or field_key == CardSearchResult.stupid_map("names"):
                used_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('name', flat=True)
                return KnownName.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "teams" or field_key == CardSearchResult.stupid_map("teams"):
                used_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('team', flat=True)
                return Team.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "cities" or field_key == CardSearchResult.stupid_map("cities"):
                used_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('city', flat=True)
                return City.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "attribs" or field_key == CardSearchResult.stupid_map("attribs"):
                return #TODO
            elif field_key == "condition":
                used_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('condition', flat=True)
                return City.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "parallel" or field_key == CardSearchResult.stupid_map("parallel"):
                used_values = CardSearchResult.objects.filter(parent_card__collection=collection_id).values_list('parallel', flat=True)
                return Parallel.objects.filter(raw_value__in=used_values).distinct().order_by
            elif field_key == "status":            
                return [StatusBase.get_meta(status)["icon"] for status in StatusBase]  #all statuses
        except CardSearchResult.DoesNotExist as e:
            print("Warning no options for collection:", e)
            return []
    elif csrId:
        csr = CardSearchResult.objects.get(id=csrId)
        if field_key == "brands" or field_key == CardSearchResult.stupid_map("brands"):
            return [obj.raw_value for obj in csr.brands.all()]
        elif field_key == "subsets" or field_key == CardSearchResult.stupid_map("subsets"):
            return [(obj.parent_brand.raw_value, obj.raw_value) for obj in csr.subsets.all()]
        elif field_key == "names" or field_key == CardSearchResult.stupid_map("names"):
            return [obj.raw_value for obj in csr.names.all()]
        elif field_key == "teams" or field_key == CardSearchResult.stupid_map("teams"):
            return [obj.raw_value for obj in csr.teams.all()]
        elif field_key == "cities" or field_key == CardSearchResult.stupid_map("cities"):
            return [obj.raw_value for obj in csr.cities.all()]
        elif field_key == "attribs" or field_key == CardSearchResult.stupid_map("attribs"):
            return [opt for opt in csr.get_individual_options("attribs")]
        elif field_key == "condition" or field_key == CardSearchResult.stupid_map("condition"):
            return [obj.raw_value for obj in csr.condition.all()]
        elif field_key == "parallel" or field_key == CardSearchResult.stupid_map("parallel"):
            return [obj.raw_value for obj in csr.parallel.all()]
        
    else:
        #if no specific CSR Is passed, we just return everything
        if field_key == "brands" or field_key == CardSearchResult.stupid_map("brands"):
            return [obj.raw_value for obj in Brand.objects.order_by("raw_value")]
        elif field_key == "subsets" or field_key == CardSearchResult.stupid_map("subsets"):
            return [(obj.parent_brand.raw_value, obj.raw_value) for obj in Subset.objects.order_by("raw_value")]
        elif field_key == "names" or field_key == CardSearchResult.stupid_map("names"):
            return [obj.raw_value for obj in KnownName.objects.order_by("raw_value")]
        elif field_key == "teams" or field_key == CardSearchResult.stupid_map("teams"):
            return [obj.raw_value for obj in Team.objects.order_by("raw_value")]
        elif field_key == "cities" or field_key == CardSearchResult.stupid_map("cities"):
            return [obj.raw_value for obj in City.objects.order_by("raw_value")]
        elif field_key == "attribs" or field_key == CardSearchResult.stupid_map("attribs"):
            #TODO: move this into SettingsToken
            return [obj.primary_token.raw_value for obj in CardAttribute.objects.filter(primary_token_id=F("id")).order_by("raw_value")]
        elif field_key == "condition" or field_key == CardSearchResult.stupid_map("condition"):
            return [obj.raw_value for obj in Condition.objects.filter(primary_token_id=F("id")).order_by("raw_value")]
        elif field_key == "parallel" or field_key == CardSearchResult.stupid_map("parallel"):
            return [obj.raw_value for obj in Parallel.objects.order_by("raw_value")]
        elif field_key == "status":            
            #print([StatusBase.get_meta(status)["icon"] for status in StatusBase])
            return [StatusBase.get_meta(status)["icon"] for status in StatusBase]
