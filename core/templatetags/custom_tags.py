from django import template
from core.models.CardSearchResult import CardSearchResult
from core.models.Card import Collection
from services.models import Brand, KnownName, Team, City,CardAttribute, Subset

register = template.Library()

@register.filter
def get_attribute(obj, attr):
    return getattr(obj, attr, None)

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
        print(key, CardSearchResult.stupid_map(key))
        options = d.get(CardSearchResult.stupid_map(key), None)
        return sorted(options, reverse=True)
    except (TypeError, AttributeError):
        return None

@register.simple_tag
def get_collections():
    return Collection.objects.order_by('-id')

@register.simple_tag
def get_autocomplete_options(field_key):
    print(field_key)
    if field_key == "brands":
        return [obj.raw_value for obj in Brand.objects.order_by("raw_value")]
    elif field_key == "subsets":
        return [(obj.parent_brand.raw_value, obj.raw_value) for obj in Subset.objects.order_by("raw_value")]
    elif field_key == "names":
        return [obj.raw_value for obj in KnownName.objects.order_by("raw_value")]
    elif field_key == "teams":
        return [obj.raw_value for obj in Team.objects.order_by("raw_value")]
    elif field_key == "cities":
        return [obj.raw_value for obj in City.objects.order_by("raw_value")]
    elif field_key == "attribs":
        return [obj.raw_value for obj in CardAttribute.objects.order_by("raw_value")]

@register.simple_tag(takes_context=True)
def build_title(context, fields=None):
    print("context:", context)
    print(fields)
    return context["card"][1].build_title(fields)
