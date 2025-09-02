from django.db import models
import re
from core.models.Cropping import CropParams
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Settings, CardNumber, Season, SerialNumber, Condition, Parallel, CardName
from collections import defaultdict, Counter
import requests
from services import ebay
import statistics

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
    
        #print("Setting:", field_to_set, "=", value)
        #print("Setting:", is_manual_fieldname, "=", is_manual)

        setattr(self, field_to_set, value)
        setattr(self, is_manual_fieldname, is_manual)

        try:
            self.save()
        except Exception as e:
            print(f"❌ Save failed: {e}")
    
    def __getattr__(self, name):
        #print("getattr", name)
        if name.startswith("display_"):
            field = name[len("display_"):]
            try:
                return self.display_value(field)
            except AttributeError:
                raise AttributeError(f"Override fields for '{field}' not found.")
            
        try:
            return super().__getattribute__(name)
        except AttributeError:
            raise AttributeError(f"'{name}' not found.")

    
    def display_value(self, field, display_flag=None):
        flag = False
        #print("dsisplay val",  self, field, display_flag)
        if hasattr(self, f"{field}_is_manual"):
            flag = getattr(self, f"{field}_is_manual") if display_flag is None else display_flag
        #print("final disp", flag)
        return self.manual_value(field) if flag else self.default_value(field)
    
    def default_value(self, field):
        #print("default val", self, field)
        return getattr(self, field)
    
    def manual_value(self, field):
        #print("manuel", self, field)
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

    card_name = models.CharField(max_length=100, blank=True)
    card_name_m = models.CharField(max_length=100, blank=True)
    card_name_is_manual = models.BooleanField(default=False)

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
    parallel_is_manual = models.BooleanField(default=False)
    
    title_to_be = models.CharField(max_length=100, blank=True)
    title_to_be_m = models.CharField(max_length=100, blank=True)
    title_to_be_is_manual = models.BooleanField(default=False)

    attributes = models.TextField(blank=True)
    unknown_words = models.TextField(blank=True)   
    collapsed_tokens = models.JSONField(default=dict, blank=True)
    response_count = models.IntegerField(default=0)
    condition = models.CharField(max_length=100, blank=True)

    attribute_flags = models.JSONField(default=list)

    #maybe this should be a full CSR object?  Would you ever Search by back?  But that makes displayu easier
    front_crop_params = models.OneToOneField(CropParams,  on_delete=models.CASCADE, related_name="csr_as_front", null=True)
    reverse_crop_params = models.OneToOneField(CropParams,  on_delete=models.CASCADE, related_name="csr_as_reverse", null=True)

    search_string = models.TextField(max_length=250, blank=True)

    #these are listing specific thus far
    sport = models.CharField(max_length=100, blank=True)
    league = models.CharField(max_length=100, blank=True)
    full_set = models.CharField(max_length=100, blank=True)
    full_team = models.CharField(max_length=100, blank=True)
    features = models.CharField(max_length=100, blank=True)
    ebay_listing_id = models.CharField(max_length=50, blank=True)
    ebay_item_id = models.CharField(max_length=50, blank=True)
    ebay_offer_id = models.CharField(max_length=50, blank=True)
    list_price = models.FloatField(default=0.0)

    ebay_mean_price = models.FloatField(default=0.0)
    ebay_median_price = models.FloatField(default=0.0)
    ebay_mode_price = models.FloatField(default=0.0)
    ebay_low_price = models.FloatField(default=0.0)
    ebay_high_price = models.FloatField(default=0.0)


    #combine all this into field_definition
    readonly_fields = ["search_string", "response_count", "ebay_item_id",  "ebay_listing_id", "ebay_offer_id"]

    overrideable_fields = [
        "full_name", "first_name", "last_name",
        "year", "brand", "subset", "parallel",
        "card_number", "team", "city", "serial_number", "title_to_be", "card_name"
    ]

    display_fields = [
        "year", "brand", "subset", "parallel", "full_name", 
        "card_number", "card_name", "city", "team", "serial_number", "condition", 
        "attributes", "unknown_words", 
        "ebay_mean_price", "ebay_median_price", "ebay_mode_price", "ebay_low_price", "ebay_high_price",  #"search_string", "response_count", "first_name", "last_name",
    ]

    calculated_fields = ["title_to_be"]

    text_fields = ["unknown_words"]

    listing_fields = ["full_name", "first_name", "last_name",
        "year", "brand", "subset",
        "card_number", "team", "city", "serial_number", 
        "attributes", "unknown_words", "title_to_be"
    ]

    #TODO: read this 
    checkbox_fields = ["attributes"]


    dynamic_listing_fields = ["front", "back"]

    def save(self, *args, **kwargs):
        # Auto-generate title before saving
        self.sport = ""
        self.league = ""
        self.full_set = self.build_full_set()
        self.full_team = self.build_full_team()
        if self.attributes:
            print(self.attributes)
            print(self.attribute_flags)
            self.features = " | ".join(key for key in self.attribute_flags.keys())
            print(self.features)
        #self.title_to_be = f"{self.display_value("year")} {self.display_value("brand")} {self.display_value("full_name")} {self.display_value("city")} {self.display_value("team")}"
        super().save(*args, **kwargs)

    @classmethod
    def stupid_map(cls, key):
        #TODO:get rid of this when you can
        if key == "year":
            return "year"
        elif key == "year":
            return "year"
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
        elif key == "card_name":
            return "card_name"
        else:
            return "unknown_words"

    def get_latest_front(self):
        return self.parent_card.cropped_image.path()
    
    def get_individual_options(self, field_key):
        return [token[2] for token in self.collapsed_tokens.get(field_key, [])]

    def get_latest_reverse(self):
        return self.parent_card.cropped_reverse.path()
    
    def aggregate_pricing_info(self):
        
        prices = [listing.ebay_price for listing in self.listings.all()]
        self.ebay_mean_price = statistics.mean(prices)
        self.ebay_median_price = statistics.median(prices)
        self.ebay_mode_price = statistics.mode(prices)
        self.ebay_low_price = min(prices)
        self.ebay_high_price = max(prices)
        self.save()


    def collapse_token_maps(self, listing_set=None):
        aggregate = defaultdict(Counter)  # key -> Counter of string values
        if listing_set is None:
            listing_set = self.listings.all()

        # Step 0: Aggregate token counts
        for listing in listing_set:

            token_list = list(listing.title.brand_tokens.all()) + list(listing.title.subset_tokens.all()) + \
                list(listing.title.team_tokens.all()) + list(listing.title.city_tokens.all()) + \
                list(listing.title.known_name_tokens.all()) + list(listing.title.card_attribute_tokens.all()) + \
                list(listing.title.condition_tokens.all()) + list(listing.title.parallel_tokens.all()) + list(listing.title.card_name_tokens.all()) + \
                listing.title.serial_number_tokens + listing.title.card_number_tokens + listing.title.season_tokens      

            print("raw: ", token_list)
            for token in token_list:
                if token.primary_token:#tokens without primarytokens are garbage words
                    aggregate[token.field_key][token.primary_token.raw_value] += 1

            for token in listing.title.unknown_tokens:
                aggregate["unknown_words"][token] += 1

        # Step 1: Build summary output with percentages
        summary = {}
        total = self.response_count
        for key, counter in aggregate.items():
            summary[key] = [
                (count, round((count / total) * 100), val)
                for val, count in counter.items()
            ]

        # Flatten all unknown tokens across listings
        unknown_tokens = [
            token
            for listing in listing_set
            for token in listing.title.unknown_tokens
        ]

        # Add to summary as a single tuple
        #summary["unknown_words"] = [(1, 100, ", ".join(unknown_tokens))]

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
                elif field_name in self.checkbox_fields:
                    print(counter)
                    #TODO obviously remove this hardcode; the value 5 should be a % based on occurrence count/total listings
                    final_value = {key[0]: True for key in counter.items() if key[1] > 5}
                    field_name = "attribute_flags"#TODO obviously remove this hardcode
                else:
                    most_common = counter.most_common(1)
                    if most_common:
                        final_value = most_common[0][0]

                print(f"Setting {field_name} to value: {final_value}")
                setattr(self, field_name, final_value)
        
        self.set_ovr_attribute("title_to_be", self.build_title(), False)
        self.save()
        print("Final collapsed tokens:", self.collapsed_tokens)
        return summary



    def update_fields(self, all_field_data):
        print("afd", all_field_data)
        for field_name, field_value in all_field_data.items():
            if field_name in ['csrfmiddlewaretoken', 'new_field', 'new_value', 'csrId']:
                continue
            
            #check for compound names (checkbox groups, etc)
            if hasattr(self, field_name) or hasattr(self, field_name[:field_name.find('.')]):
                #print("has attr", field_name, field_value, self.overrideable_fields)
                if field_name in self.overrideable_fields:    
                    #print("over")
                    #print(field_name, field_value, all_field_data[f"{field_name}_is_manual"])                
                    is_manual = all_field_data.get(f"{field_name}_is_manual", True)
                    self.set_ovr_attribute(field_name, field_value, is_manual)
                elif field_name.find('.') > 0:#checkbox groups
                    group_name, field_name = field_name.split('.')                     
                    #print(group_name, field_name)
                    #TODO: need to make this more generic to handle additional checkhbox fields
                    if group_name == 'attributes':
                        print('checkboxes')
                        print(field_name, type(field_value), field_value)
                        #if field_name in self.attribute_flags:
                        self.attribute_flags[field_name] = (field_value.lower() == 'true')
                        #else:
                        print(self.attribute_flags)

                else:
                    #print("setting", field_name, field_value)
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
        listing_set = []
        if not items is None:
            for idx, item in enumerate(items, 1): 
                listing = ProductListing.from_search_results(item, csr, tokenize)
                listing_set.append(listing)
            csr.response_count = len(items)
            if tokenize:
                #must pass the listings here to preserve the in memory attributes
                csr.collapsed_tokens = csr.collapse_token_maps(listing_set)
                csr.aggregate_pricing_info()
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
            isRC = "RC" if "RC" in self.display_value("attributes") else ""
        else:            
            year = fields["year"]
            brand = fields["brand"]
            subset = fields["subset"]
            name = fields["full_name"]
            serial = fields["serial"]
            nr = fields["nr"]
            city = fields["city"]
            team = fields["team"]
            isRC = "RC" if "RC" in self.fields("attribs") else ""

        subset = "" if subset == "-" else subset
        serial = "" if serial == "-" else serial
        print (f"hi: {year} {brand} {subset} {name} {serial} #{nr} {city} {team}")
        return f"{year} {brand} {subset} {name} {isRC} {serial} #{nr} {city} {team}".replace("  ", " ")

    #TODO:these buildable fields should be configurable
    def build_full_set(self, fields=None):
        print("fields:", fields)
        if not fields:
            year = self.display_value("year")
            brand = self.display_value("brand")
            subset = self.display_value("subset")
        else:            
            year = fields["year"]
            brand = fields["brand"]
            subset = fields["subset"]

        subset = "" if subset == "-" else subset
        print (f"build_full_set: {year} {brand} {subset}")
        return f"{year} {brand} {subset}".strip()
    
    #TODO:these buildable fields should be configurable
    def build_full_team(self, fields=None):
        print("fields:", fields)
        if not fields:
            city = self.display_value("city")
            team = self.display_value("team")
        else:            
            city = fields["city"]
            team = fields["team"]

        print (f"build_full_team: {city} {team}")
        return f"{city} {team}"
    
    #TODO:Too many saves
    def build_sku(self):
        full_set = self.build_full_set()
        self.sku = f"{full_set} {self.display_value('full_name')}".replace(" ", "-").upper()
        self.save()
        return self.sku

    def get_search_strings(self):
        return self.display_value("title_to_be")
    
    #TODO: This has grown enough now to condense
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
    
    def export_to_template(self, sku, template, image_links):
        
        def resolve(value):
            if isinstance(value, str) and value:
                return getattr(self, value, value)
            return value

        def traverse(data):
            if isinstance(data, dict):
                return {k: traverse(resolve(v)) for k, v in data.items()}
            elif isinstance(data, list):
                return [traverse(resolve(item)) for item in data]
            else:
                return resolve(data)

        #TODO: this is a fucking disaster
        
        filled_template = traverse(template)
        filled_template["sku"] = sku
        filled_template["product"]["aspects"]["Autographed"] = "Yes" if "Auto" in self.attributes else "No"
        filled_template["condition"] = "USED_VERY_GOOD"

        #if self.condition
        condition_token = Condition.objects.get(raw_value=self.condition)
        condition_descriptor = [
            {
                "name": 40001,
                "values": [int(condition_token.ebay_id_value)]
            }
        ]
        filled_template["conditionDescriptors"] = condition_descriptor
        filled_template["product"]["aspects"]["Card Condition"] = condition_token.ebay_string_value
        filled_template["product"]["aspects"]["Sport"] = "Baseball"
        filled_template["product"]["aspects"]["League"] = "MLB"
        filled_template["product"]["imageUrls"] = image_links

        #need to backfill these all to lists
        for field in filled_template["product"]["aspects"]:
            filled_template["product"]["aspects"][field] = [filled_template["product"]["aspects"][field]]
        #filled_template["product"]["aspects"]["Condition"] = ["Ungraded"]        
        return filled_template
    


    def check_inventory_item_exists(self, sku, token):
        url = f"https://api.ebay.com/sell/inventory/v1/inventory_item/{sku}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers)
        print(response.text)
        return response.status_code == 200

    def check_category_metadata(self, id, token):
            url = "https://api.ebay.com/sell/metadata/v1/marketplace/EBAY_US/get_item_condition_policies?filter=261328"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            print("category:", response.text[:2000])
            #print("jason:", response.json()["itemConditionPolicies"])
            for policy in response.json()["itemConditionPolicies"]:#.get("itemConditionPolicies"):
                if policy["categoryId"] == "261328":
                    print(policy)
                    
                    return None

            #print("det: ", response.json()["itemConditionPolicies"])

    def get_offer(self, id, token):
            url = f"https://api.ebay.com/sell/inventory/v1/offer/{id}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers)
            print("offer: ", response.text)

    def retokenize(self):
        applied_settings = Settings.get_default()
        print(self)
        listing_set = self.listings.all()
        for listing in listing_set:
            #title = listing.title
            #print("title ID: ", listing.title.id)
            listing.title.tokenize(applied_settings)
            #print("After tokenize:", listing.title.serial_number_tokens)

        self.collapse_token_maps(listing_set)
        self.aggregate_pricing_info()


class ProductListing(models.Model):

    item_id = models.CharField(max_length=100, blank=True)
    listing_date = models.DateTimeField(blank=False)
    img_url = models.CharField(max_length=250, blank=False)
    thumb_url = models.CharField(max_length=250, blank=False)    #title is declared above
    ebay_price = models.FloatField(default=0.0)

    search_result = models.ForeignKey(CardSearchResult, on_delete=models.CASCADE, default=1, related_name="listings")    

    @classmethod
    def from_search_results(cls, item, parent_csr, tokenize=True):
        print("my item", item)
        listing = cls()
        listing.item_id = item.get("itemId", "N/A")
        listing.listing_date = item.get("itemCreationDate")
        listing.img_url = item.get("itemWebUrl", "No thumbnail")
        listing.thumb_url = item.get("thumbnailImages", [{}])[0].get("imageUrl", "No thumbnail")
        listing.ebay_price = item.get("price", [{}]).get("value", "-1")
        listing.search_result = parent_csr
        listing.save()
        listing.title = ListingTitle.objects.create(title=item.get("title", "No title"), parent_listing=listing)
        
        #TODO:ultimately this will need to be updated to handle multiple settings objects
        if tokenize:
            listing.title.tokenize(Settings.get_default())

        return listing

            
  
class ListingTitle(models.Model):
    title = models.CharField(max_length=100, blank=True)
    tokens = models.JSONField(default=dict, blank=True)
    
    parent_listing = models.OneToOneField(ProductListing, on_delete=models.CASCADE, default=1, related_name="title")  
    
    #TODO: needs condensing down in to a generic token reference at least
    brand_tokens = models.ManyToManyField(Brand, blank=True, related_name="listing_titles")
    subset_tokens = models.ManyToManyField(Subset, blank=True, related_name="listing_titles")
    team_tokens = models.ManyToManyField(Team, blank=True, related_name="listing_titles")   
    city_tokens = models.ManyToManyField(City, blank=True, related_name="listing_titles")
    known_name_tokens = models.ManyToManyField(KnownName, blank=True, related_name="listing_titles")
    card_attribute_tokens = models.ManyToManyField(CardAttribute, blank=True, related_name="listing_titles")
    condition_tokens = models.ManyToManyField(Condition, blank=True, related_name="listing_titles")
    parallel_tokens = models.ManyToManyField(Parallel, blank=True, related_name="listing_titles")
    card_name_tokens = models.ManyToManyField(CardName, blank=True, related_name="listing_titles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serial_number_tokens = []
        self.card_number_tokens = []
        self.season_tokens = []
        self.unknown_tokens = []

    #TODO: move this somewhere else
    def normalize_word(self, word):
    # Strip leading "#" if it's a card number (e.g. "#23" → "23")
        if word.startswith("#") and any(char.isdigit() for char in word):
            return word[1:]
        return word

    def tokenize(self, applied_settings):
        tokens = {}
        print(self.id)
        #this logic relies on the fact that the "key" must match something defined by reading in settings.  Thus, don't change these
        temp_title, tokens, self.season_tokens = Season.match_extract(self.title, tokens, "year", applied_settings, return_first_match=False)
        print("New tokens: ", self.season_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Brand.match_extract(temp_title, tokens, "brands", applied_settings)
        self.brand_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Parallel.match_extract(temp_title, tokens, "parallel", applied_settings)
        self.parallel_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = KnownName.match_extract(temp_title, tokens, "names", applied_settings)
        self.known_name_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = City.match_extract(temp_title, tokens, "cities", applied_settings)
        self.city_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Team.match_extract(temp_title, tokens, "teams", applied_settings)
        self.team_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Condition.match_extract(temp_title, tokens, "condition", applied_settings, return_first_match=True)
        self.condition_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Subset.match_extract(temp_title, tokens, "subsets", applied_settings)
        self.subset_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = CardName.match_extract(temp_title, tokens, "card_name", applied_settings, return_first_match=True)
        self.card_name_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = CardAttribute.match_extract(temp_title, tokens, "attribs", applied_settings, return_first_match=False)
        self.card_attribute_tokens.set(new_tokens)
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        #I think these can go anywhere without conflicting with anythign except each other
        temp_title, tokens, self.card_number_tokens = CardNumber.match_extract(temp_title, tokens, "cardnr", applied_settings, return_first_match=False)
        
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, self.serial_number_tokens = SerialNumber.match_extract(temp_title, tokens, "serial", applied_settings, return_first_match=False)
         
        print("New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)

        unknown_tokens = re.findall(r'\b#?[a-z0-9]{2,}(?:-[a-z0-9]{2,})?\b', temp_title.lower())
        unknown_tokens = [self.normalize_word(t) for t in unknown_tokens if len(t) >= 3]
        self.unknown_tokens = unknown_tokens
        print ("hi", self.id)
        #self.tokens = tokens

        self.save()
        
        print(self.id)
        print ("end tokenize: ", self.serial_number_tokens)
        print ("end tokenize: ", self.card_number_tokens)
        print ("end tokenize: ", self.season_tokens)

    def __str__(self):
        return self.title

