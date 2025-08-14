from django.db import models
import re
from core.models.Cropping import CropParams
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Settings, CardNumber, Season, SerialNumber, Condition
from collections import defaultdict, Counter


class OverrideableFieldsMixin(models.Model):
    class Meta:
        abstract = True

    def set_ovr_attribute(self, field, value, is_manual):
        print("setting over: ")
        field_to_set = f"{field}_m" if is_manual else field
        is_manual_fieldname = f"{field}_is_manual"

        # Validate fields exist
        model_fields = [f.name for f in self._meta.fields]
        if field_to_set not in model_fields:
            print(f"⚠️ Field '{field_to_set}' does not exist on model.")
            return
        if is_manual_fieldname not in model_fields:
            print(f"⚠️ Field '{is_manual_fieldname}' does not exist on model.")
            return

        # Coerce boolean
        if isinstance(is_manual, str):
            is_manual = is_manual.lower() in ["true", "1", "yes"]
    
        print("Setting:", field_to_set, "=", value)
        print("Setting:", is_manual_fieldname, "=", is_manual)

        setattr(self, field_to_set, value)
        setattr(self, is_manual_fieldname, is_manual)

        try:
            self.save()
        except Exception as e:
            print(f"❌ Save failed: {e}")
    
    def __getattr__(self, name):
        if name.startswith("display_"):
            field = name[len("display_"):]
            try:
                return self.display_value(field)
            except AttributeError:
                raise AttributeError(f"Override fields for '{field}' not found.")
        
        # 🔹 Fallback to regular attribute access
        try:
            return super().__getattribute__(name)
        except AttributeError:
            raise AttributeError(f"'{name}' not found.")

    
    def display_value(self, field, display_flag=None):
        flag = False
        if hasattr(self, f"{field}_is_manual"):
            flag = getattr(self, f"{field}_is_manual") if display_flag is None else display_flag
        return self.manual_value(field) if flag else self.default_value(field)
    
    def default_value(self, field):
        print(self, field)
        return getattr(self, field)
    
    def manual_value(self, field):
        return getattr(self, f"{field}_m")

class CardSearchResult(OverrideableFieldsMixin, models.Model):
    
    parent_card = models.ForeignKey("core.Card", on_delete=models.CASCADE, default=1, related_name="search_results") 
    #needed for backwards compat until I address the name knot
    name = models.CharField(max_length=100, blank=True)
    name_m = models.CharField(max_length=100, blank=True)
    name_is_manual = models.BooleanField(default=False)
    
    full_name = models.CharField(max_length=100, blank=True)
    full_name_m = models.CharField(max_length=100, blank=True)
    full_name_is_manual = models.BooleanField(default=False)
    
    full_name = models.CharField(max_length=100, blank=True)
    full_name_m = models.CharField(max_length=100, blank=True)
    full_name_is_manual = models.BooleanField(default=False)

    first_name = models.CharField(max_length=50, blank=True)
    first_name_m = models.CharField(max_length=50, blank=True)
    first_name_is_manual = models.BooleanField(default=False)

    last_name = models.CharField(max_length=50, blank=True)
    last_name_m = models.CharField(max_length=50, blank=True)
    last_name_is_manual = models.BooleanField(default=False)
    
    year = models.CharField(max_length=20, blank=True)
    year_m = models.CharField(max_length=20, blank=True)
    year_is_manual = models.BooleanField(default=False)
    
    brand = models.CharField(max_length=100, blank=True)
    brand_m = models.CharField(max_length=100, blank=True)
    brand_is_manual = models.BooleanField(default=False)
    
    subset = models.CharField(max_length=100, blank=True)
    subset_m = models.CharField(max_length=100, blank=True)
    subset_is_manual = models.BooleanField(default=False)
    
    card_number = models.CharField(max_length=50, blank=True)
    card_number_m = models.CharField(max_length=50, blank=True)
    card_number_is_manual = models.BooleanField(default=False)
    
    team = models.CharField(max_length=100, blank=True)
    team_m = models.CharField(max_length=100, blank=True)
    team_is_manual = models.BooleanField(default=False)
    
    city = models.CharField(max_length=100, blank=True)
    city_m = models.CharField(max_length=100, blank=True)
    city_is_manual = models.BooleanField(default=False)
    
    serial_number = models.CharField(max_length=50, blank=True)
    serial_number_m = models.CharField(max_length=50, blank=True)
    serial_number_is_manual = models.BooleanField(default=False)
    
    parallel = models.CharField(max_length=50, blank=True)
    parallel_m = models.CharField(max_length=50, blank=True)
    parallel_manual = models.BooleanField(default=False)
    
    title_to_be = models.CharField(max_length=100, blank=True)
    title_to_be_m = models.CharField(max_length=100, blank=True)
    title_to_be_is_manual = models.BooleanField(default=False)

    attributes = models.TextField(blank=True)    
    unknown_words = models.TextField(blank=True)   
    collapsed_tokens = models.JSONField(default=dict, blank=True)
    response_count = models.IntegerField(default=0)
    condition = models.CharField(max_length=100, blank=True)
    #maybe this should be a full CSR object?  Would you ever Search by back?  But that makes displayu easier
    front_crop_params = models.OneToOneField(CropParams,  on_delete=models.CASCADE, related_name="csr_as_front", null=True)
    reverse_crop_params = models.OneToOneField(CropParams,  on_delete=models.CASCADE, related_name="csr_as_reverse", null=True)

    search_string = models.TextField(max_length=250, blank=True)

    #combine all this into field_definition
    readonly_fields = ["search_string", "response_count"]

    overrideable_fields = [
        "full_name", "first_name", "last_name",
        "year", "brand", "subset", 
        "card_number", "team", "city", "serial_number", "title_to_be", "parallel"
    ]

    display_fields = [
        "year", "brand", "subset", "parallel", "full_name", 
        "card_number", "city", "team", "serial_number", "condition", 
        "attributes", "unknown_words"#"search_string", "response_count", "first_name", "last_name",
    ]

    calculated_fields = ["title_to_be"]

    text_fields = ["attributes", "unknown_words", "condition"]

    listing_fields = ["full_name", "first_name", "last_name",
        "year", "brand", "subset",
        "card_number", "team", "city", "serial_number", 
        "attributes", "unknown_words", "title_to_be"
    ]

    dynamic_listing_fields = ["front", "back"]

    def save(self, *args, **kwargs):
        # Auto-generate title before saving
        #self.title_to_be = f"{self.display_value("year")} {self.display_value("brand")} {self.display_value("full_name")} {self.display_value("city")} {self.display_value("team")}"
        super().save(*args, **kwargs)

    @classmethod
    def stupid_map(cls, key):
        #get rid of this when you can
        if key == "season":
            return "year"
        elif key == "year":
            return "season"
        elif key == "subsets":
            return "subset"
        elif key == "subset":
            return "subsets"
        elif key == "teams":
            return "team"
        elif key == "team":
            return "teams"
        elif key == "cities":
            return "city"
        elif key == "city":
            return "cities"
        elif key == "cardnr":
            return "card_number"
        elif key == "card_number":
            return "cardnr"
        elif key == "serial":
            return "serial_number"
        elif key == "serial_number":
            return "serial"
        elif key == "attribs":
            return "attributes"
        elif key == "attributes":
            return "attribs"
        elif key == "brands":
            return "brand"
        elif key == "brand":
            return "brands"
        elif key == "names":
            return "full_name"
        elif key == "full_name":
            return "names"
        elif key == "condition":
            return "condition"
        elif key == "parallel":
            return "parallel"
        else:
            return "unknown_words"

    def get_latest_front(self):
        return self.parent_card.cropped_image.path()
    
    def get_cardnr_options(self):
        return [token[2] for token in self.collapsed_tokens.get("cardnr", [])]

    def get_latest_reverse(self):
        return self.parent_card.cropped_reverse.path()

    def collapse_token_maps(self):
        aggregate = defaultdict(Counter)  # key -> Counter of string values

        # Step 0: Aggregate token counts
        for listing in self.listings.all():
            raw_json = getattr(listing.title, "tokens", {})
            if isinstance(raw_json, dict):
                for field, values in raw_json.items():
                    if isinstance(values, list) and all(isinstance(v, str) for v in values):
                        for val in values:
                            aggregate[field][val] += 1

        # Step 1: Build summary output with percentages
        summary = {}
        for key, counter in aggregate.items():
            total = sum(counter.values())
            summary[key] = [
                (count, round((count / total) * 100), val)
                for val, count in counter.items()
            ]

        print("Aggregate with percentages:")
        for field, entries in summary.items():
            print(f"{field}:")
            for count, percent, val in entries:
                print(f"  {val}: {count} ({percent}%)")

        # Step 2: Set most frequent token on model (if applicable)
        for field_key, counter in aggregate.items():
            field_name = self.stupid_map(field_key)
            print(f"Processing stupid field: {field_key} smart field: {field_name} with {len(counter)} unique tokens")

            if hasattr(self, field_name):
                field = self._meta.get_field(field_name)
                print(type(field), field_name, field)

                if field_name in self.text_fields:
                    final_value = ", ".join(x for x in counter.keys())
                else:
                    most_common = counter.most_common(1)
                    if most_common:
                        final_value = most_common[0][0]

                print(f"Setting {field_name} to value: {final_value}")
                setattr(self, field_name, final_value)

        self.set_ovr_attribute("title_to_be", self.build_title(), False)
        self.save()  # persist changes after setting fields
        return summary


    def update_fields(self, all_field_data):
        print("afd", all_field_data)
        for field_name, field_value in all_field_data.items():
            if field_name in ['csrfmiddlewaretoken', 'new_field', 'new_value', 'csrId']:
                continue
            
            if hasattr(self, field_name):
                print("has attr", field_name, field_value, self.overrideable_fields)
                if field_name in self.overrideable_fields:    
                    print("over")
                    #print(field_name, field_value, all_field_data[f"{field_name}_is_manual"])                
                    is_manual = all_field_data.get(f"{field_name}_is_manual", True)
                    self.set_ovr_attribute(field_name, field_value, is_manual)
                else:
                    print("setting", field_name, field_value)
                    setattr(self, field_name, field_value)
        self.save()

    @classmethod
    def create_empty(cls, pcard):
            print(f"Processing 0 search results for card {pcard.id}")
            csr = CardSearchResult(parent_card = pcard)
            csr.front_crop_params = CropParams.clone(pcard.cropped_image.crop_params.last())
            csr.reverse_crop_params = CropParams.clone(pcard.cropped_reverse.crop_params.last())
            csr.response_count = 0
            csr.save()
            return csr
        
    @classmethod
    def from_search_results(cls, pcard, items=None, tokenize=True):
        csr = cls.create_empty(pcard)
            
        if not items is None:
            for idx, item in enumerate(items, 1): 
                ProductListing.from_search_results(item, csr, tokenize)
            csr.result_count = len(items)
            if tokenize:
                csr.collapsed_tokens = csr.collapse_token_maps()
                print(csr.collapsed_tokens)
            csr.save()
        return csr
        
    def build_title(self, fields=None):
        print("fields:", fields)
        if not fields:
            year = self.display_value("year")
            brand = self.display_value("brand")
            subset = self.display_value("subset")
            name = self.display_value("full_name")
            serial = self.display_value("serial_number")
            nr = self.display_value("card_number")
            city = self.display_value("city")
            team = self.display_value("team")
        else:            
            year = fields["year"]
            brand = fields["brand"]
            subset = fields["subset"]
            name = fields["full_name"]
            serial = fields["serial"]
            nr = fields["nr"]
            city = fields["city"]
            team = fields["team"]

        subset = "" if subset == "-" else subset
        serial = "" if serial == "-" else serial
        print (f"hi: {year} {brand} {subset} {name} {serial} #{nr} {city} {team}")
        return f"{year} {brand} {subset} {name} {serial} #{nr} {city} {team}"


    def get_search_strings(self):
        return self.display_value("title_to_be")
    
    def export_to_csv_string(self, field_map):
        csr_fields = ""
        for dest_field_name, my_field_name in field_map.items():
            
            if my_field_name != "":
                csr_fields += getattr(self, my_field_name)
            csr_fields += ","
        return csr_fields
    
    def export_to_csv(self, field_map):
        csr_fields = []
        for dest_field_name, my_field_name in field_map.items():
            
            if my_field_name != "":
                csr_fields.append(self.display_value(my_field_name))
            else:
                csr_fields.append("")
            
        return csr_fields

    def retokenize(self):
        applied_settings = Settings.get_default()
        print(self)
        for listing in self.listings.all():
            print(listing.id)
            listing.title.tokenize(applied_settings)
        self.collapse_token_maps()


class ProductListing(models.Model):

    item_id = models.CharField(max_length=100, blank=True)
    listing_date = models.DateTimeField(blank=False)
    img_url = models.CharField(max_length=250, blank=False)
    thumb_url = models.CharField(max_length=250, blank=False)    #title is declared above

    search_result = models.ForeignKey(CardSearchResult, on_delete=models.CASCADE, default=1, related_name="listings")    

    @classmethod
    def from_search_results(cls, item, parent_csr, tokenize=True):
        print("my item", item)
        listing = cls()
        listing.item_id = item.get("itemId", "N/A")
        listing.listing_date = item.get("itemCreationDate")
        listing.img_url = item.get("itemWebUrl", "No thumbnail")
        listing.thumb_url = item.get("thumbnailImages", [{}])[0].get("imageUrl", "No thumbnail")
        listing.search_result = parent_csr
        listing.save()
        listing.title = ListingTitle.objects.create(title=item.get("title", "No title"), parent_listing=listing)
        
        #ultimately this will need to be updated to handle multiple settings objects
        if tokenize:
            listing.title.tokenize(Settings.get_default())

            

    
class ListingTitle(models.Model):
    title = models.CharField(max_length=100, blank=True)
    tokens = models.JSONField(default=dict, blank=True)
    parent_listing = models.OneToOneField(ProductListing, on_delete=models.CASCADE, default=1, related_name="title")  
    
    #move this somewhere else
    def normalize_word(self, word):
    # Strip leading "#" if it's a card number (e.g. "#23" → "23")
        if word.startswith("#") and any(char.isdigit() for char in word):
            return word[1:]
        return word

    def tokenize(self, applied_settings):
        tokens = {}
        print(self.id)
        #this logic relies on the fact that the "key" must match something defined by reading in settings.  Thus, don't change these
        temp_title, tokens = Season.match_extract(self.title, tokens, "season", applied_settings, return_first_match=False)
        print(temp_title)
        print(tokens)
        temp_title, tokens = Brand.match_extract(temp_title, tokens, "brands", applied_settings)
        print(temp_title)
        print(tokens)
        temp_title, tokens = KnownName.match_extract(temp_title, tokens, "names", applied_settings)  
        print(temp_title)
        print(tokens)
        temp_title, tokens = City.match_extract(temp_title, tokens, "cities", applied_settings)
        print(temp_title)
        print(tokens)
        temp_title, tokens = Team.match_extract(temp_title, tokens, "teams", applied_settings)
        print(temp_title)
        print(tokens)
        temp_title, tokens = Condition.match_extract(temp_title, tokens, "condition", applied_settings, return_first_match=False)
        print(temp_title)
        print(tokens)
        temp_title, tokens = Subset.match_extract(temp_title, tokens, "subsets", applied_settings)
        print(temp_title)
        print(tokens)
        temp_title, tokens = CardAttribute.match_extract(temp_title, tokens, "attribs", applied_settings, return_first_match=False)
        print(temp_title)
        print(tokens)

        #I think these can go anywhere without conflicting with anythign except each other
        temp_title, tokens = CardNumber.match_extract(temp_title, tokens, "cardnr", applied_settings, return_first_match=False)
        print(temp_title)
        print(tokens)
        temp_title, tokens = SerialNumber.match_extract(temp_title, tokens, "serial", applied_settings, return_first_match=False)
        print(temp_title)
        print(tokens)

        unknown_tokens = re.findall(r'\b#?[a-z0-9]{2,}(?:-[a-z0-9]{2,})?\b', temp_title.lower())
        unknown_tokens = [self.normalize_word(t) for t in unknown_tokens if len(t) >= 3]
        tokens["unknown"] = unknown_tokens
        print ("hi", self.id)
        self.tokens = tokens
        self.save()

    def __str__(self):
        return self.title

