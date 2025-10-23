from django.db import models
import re, requests, statistics
from core.models.Cropping import CropParams
from core.models.Status import *
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, Settings, CardNumber, Season, SerialNumber, Condition, Parallel, CardName
from collections import defaultdict, Counter
from services import settings_management as app_settings
from datetime import datetime

class OverrideableFieldsMixin(models.Model):
    class Meta:
        abstract = True

    def add_token_link(self, field, value, select=False, all_field_data={}):
        #print("add token link: ", field, value, select)
        available_tokens_fieldname = f"{field}_available_tokens"
        selected_token_fieldname = f"{field}_selected_token"        
        selected_token = None
        #print("c:", available_tokens_fieldname, selected_token_fieldname)
        #TODO:This is going to be extra slow of course; don't search through every name every time
        if hasattr(self, available_tokens_fieldname) and hasattr(self, selected_token_fieldname):
            avail_token_manager = getattr(self, available_tokens_fieldname)
            if avail_token_manager and avail_token_manager.filter(raw_value__iexact=value).exists():
                selected_token = avail_token_manager.get(raw_value__iexact=value)
            else:
                selected_token = app_settings.add_token(field, value, all_field_data, user_settings=None)
                avail_token_manager.add(selected_token)
            
            if select: 
                setattr(self, selected_token_fieldname, selected_token)
        else:
            print("link not found", available_tokens_fieldname, selected_token_fieldname)
        return selected_token

    def set_ovr_attribute(self, field, new_field_value, is_manual, all_field_data={}):
        #print("setting over: ", field)
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

        print("Setting:", field_to_set, "=", new_field_value)
        print("Setting:", is_manual_fieldname, "=", is_manual)
        
        if new_field_value:
            setattr(self, field_to_set, new_field_value)
            
        else:
            setattr(self, field_to_set, None)

        setattr(self, is_manual_fieldname, is_manual)

        #remove this hardcode
        if not field in self.calculated_fields:
            self.add_token_link(field, new_field_value, True, all_field_data)

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
    #TODO: this class needs to be broken up
    parent_card = models.ForeignKey("core.Card", on_delete=models.CASCADE, default=1, related_name="search_results") 
    #needed for backwards compat until I address the name knot
    name = models.CharField(max_length=100, blank=True)
    name_m = models.CharField(max_length=100, blank=True)
    name_is_manual = models.BooleanField(default=False)
    
    full_name = models.CharField(max_length=100, blank=True, null=True)
    full_name_m = models.CharField(max_length=100, blank=True, null=True)
    full_name_is_manual = models.BooleanField(default=False)
    full_name_available_tokens = models.ManyToManyField(KnownName, blank=True, related_name="csr_as_available_full_name")
    full_name_selected_token = models.ForeignKey(KnownName, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_full_name")
    
    year = models.CharField(max_length=20, blank=True, null=True)
    year_m = models.CharField(max_length=20, blank=True, null=True)
    year_is_manual = models.BooleanField(default=False)
    year_available_tokens = models.ManyToManyField(Season, blank=True, related_name="csr_as_available_year")
    year_selected_token = models.ForeignKey(Season, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_year")
    
    brand = models.CharField(max_length=100, blank=True, null=True)
    brand_m = models.CharField(max_length=100, blank=True, null=True)
    brand_is_manual = models.BooleanField(default=False)
    brand_available_tokens = models.ManyToManyField(Brand, blank=True, related_name="csr_as_available_brand")
    brand_selected_token = models.ForeignKey(Brand, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_brand")
    
    subset = models.CharField(max_length=100, blank=True, null=True)
    subset_m = models.CharField(max_length=100, blank=True, null=True)
    subset_is_manual = models.BooleanField(default=False)
    subset_available_tokens = models.ManyToManyField(Subset, blank=True, related_name="csr_as_available_subset")
    subset_selected_token = models.ForeignKey(Subset, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_subset")
    
    card_number = models.CharField(max_length=50, blank=True, null=True)
    card_number_m = models.CharField(max_length=50, blank=True, null=True)
    card_number_is_manual = models.BooleanField(default=False)
    card_number_available_tokens = models.ManyToManyField(CardNumber, blank=True, related_name="csr_as_available_card_number")
    card_number_selected_token = models.ForeignKey(CardNumber, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_card_number")

    card_name = models.CharField(max_length=100, blank=True, null=True)
    card_name_m = models.CharField(max_length=100, blank=True, null=True)
    card_name_is_manual = models.BooleanField(default=False)
    card_name_available_tokens = models.ManyToManyField(CardName, blank=True, related_name="csr_as_available_card_name")
    card_name_selected_token = models.ForeignKey(CardName, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_card_name")

    team = models.CharField(max_length=100, blank=True, null=True)
    team_m = models.CharField(max_length=100, blank=True, null=True)
    team_is_manual = models.BooleanField(default=False)
    team_available_tokens = models.ManyToManyField(Team, blank=True, related_name="csr_as_available_team")
    team_selected_token = models.ForeignKey(Team, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_team")
    
    city = models.CharField(max_length=100, blank=True, null=True)
    city_m = models.CharField(max_length=100, blank=True, null=True)
    city_is_manual = models.BooleanField(default=False)
    city_available_tokens = models.ManyToManyField(City, blank=True, related_name="csr_as_available_city")
    city_selected_token = models.ForeignKey(City, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_city")
    
    serial_number = models.CharField(max_length=50, blank=True, null=True)
    serial_number_m = models.CharField(max_length=50, blank=True, null=True)
    serial_number_is_manual = models.BooleanField(default=False)    
    serial_number_available_tokens = models.ManyToManyField(SerialNumber, blank=True, related_name="csr_as_available_serial_number")
    serial_number_selected_token = models.ForeignKey(SerialNumber, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_serial_number")
    
    parallel = models.CharField(max_length=50, blank=True, null=True)
    parallel_m = models.CharField(max_length=50, blank=True, null=True)
    parallel_is_manual = models.BooleanField(default=False)    
    parallel_available_tokens = models.ManyToManyField(Parallel, blank=True, related_name="csr_as_available_parallel")
    parallel_selected_token = models.ForeignKey(Parallel, null=True, blank=True, on_delete=models.DO_NOTHING, related_name="csr_as_selected_parallel")
    
    title_to_be = models.CharField(max_length=100, blank=True)
    title_to_be_m = models.CharField(max_length=100, blank=True)
    title_to_be_is_manual = models.BooleanField(default=False)

    sold_search_string = models.CharField(max_length=100, blank=True, null=True)
    sold_search_string_m = models.CharField(max_length=100, blank=True, null=True)
    sold_search_string_is_manual = models.BooleanField(default=False)
    
    text_search_string = models.CharField(max_length=100, blank=True, null=True)
    text_search_string_m = models.CharField(max_length=100, blank=True, null=True)
    text_search_string_is_manual = models.BooleanField(default=False)
    
    filter_terms = models.CharField(max_length=250, blank=True, null=True)
    filter_terms_m = models.CharField(max_length=250, blank=True, null=True)
    filter_terms_is_manual = models.BooleanField(default=False)

    attributes = models.TextField(blank=True)
    unknown_words = models.TextField(blank=True)   
    collapsed_tokens = models.JSONField(default=dict, blank=True)
    response_count = models.IntegerField(default=0)
    condition = models.CharField(max_length=100, blank=True)

    attribute_flags = models.JSONField(default=dict)

    #maybe this should be a full CSR object?  Would you ever Search by back?  But that makes displayu easier
    front_crop_params = models.OneToOneField(CropParams,  on_delete=models.CASCADE, related_name="csr_as_front", null=True)
    reverse_crop_params = models.OneToOneField(CropParams,  on_delete=models.CASCADE, related_name="csr_as_reverse", null=True)

    #these are listing specific thus far
    sport = models.CharField(max_length=100, blank=True)
    league = models.CharField(max_length=100, blank=True)
    features = models.CharField(max_length=100, blank=True)
    ebay_listing_id = models.CharField(max_length=50, blank=True)
    ebay_item_id = models.CharField(max_length=50, blank=True)
    ebay_offer_id = models.CharField(max_length=50, blank=True, null=True)
    ebay_listing_datetime = models.DateTimeField(null=True)
    list_price = models.FloatField(default=0.0)

    ebay_mean_price = models.FloatField(default=0.0)
    ebay_median_price = models.FloatField(default=0.0)
    ebay_mode_price = models.FloatField(default=0.0)
    ebay_low_price = models.FloatField(default=0.0)
    ebay_high_price = models.FloatField(default=0.0)

    ebay_low_sold_price = models.FloatField(default=0.0)
    ebay_high_sold_price = models.FloatField(default=0.0)
    ebay_last_sold_price = models.FloatField(default=0.0)
    ebay_last_five_avg_sold_price = models.FloatField(default=0.0)
    ebay_avg_sold_price = models.FloatField(default=0.0)
    ebay_msrp = models.FloatField(default=0.0)
    

    id_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.UNEXECUTED)
    refinement_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.UNEXECUTED)
    pricing_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.UNEXECUTED)
    front_cropping_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.UNEXECUTED)
    back_cropping_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.UNEXECUTED)
    overall_status = models.CharField(max_length=20, choices=StatusBase.choices, default=StatusBase.UNEXECUTED)
    
    #combine all this into field_definition
    readonly_fields = ["response_count", "ebay_item_id",  "ebay_listing_id", "ebay_offer_id"]

    overrideable_fields = [
        "full_name", "first_name", "last_name",
        "year", "brand", "subset", "parallel",
        "card_number", "team", "city", "serial_number", 
        "title_to_be", "card_name", "text_search_string", 
        "sold_search_string", "filter_terms"
    ]

    display_fields = [
        "text_search_string", "sold_search_string", "filter_terms", "year", "brand", "subset", "parallel", "full_name", 
        "card_number", "card_name", "city", "team", "serial_number", "condition", "attributes", 
        #below only needed for expanded --> TBD
        # "ebay_mean_price", "ebay_median_price", "ebay_mode_price", "ebay_low_price", "ebay_high_price",  #"text_search_string", "response_count", "first_name", "last_name",
        # "unknown_words", 
    ]

    spreadsheet_fields = [
        "id", "title_to_be", "year", "brand", "subset", "parallel", "full_name", "ebay_msrp",
        "card_number", "card_name", "city", "team", "serial_number", "filter_terms", "condition", "attributes", 
        "ebay_mean_price", "ebay_median_price", "ebay_mode_price", "ebay_low_price", "ebay_high_price", 
        "ebay_low_sold_price", "ebay_high_sold_price", "ebay_last_sold_price", "ebay_last_five_avg_sold_price", "ebay_avg_sold_price", 
        "list_price", "ebay_listing_id", "ebay_item_id", "ebay_offer_id", "ebay_listing_datetime",         
        "text_search_string", "first_name", "last_name", "unknown_words"         
    ]

    calculated_fields = ["title_to_be", "text_search_string", "sold_search_string"]#, "filter_terms"]

    text_fields = ["unknown_words"]

    listing_fields = ["full_name", "first_name", "last_name",
        "year", "brand", "subset",
        "card_number", "team", "city", "serial_number", 
        "attributes", "unknown_words", "title_to_be"
    ]

    #TODO: read this 
    checkbox_fields = ["attributes"]
    
    dynamic_listing_fields = ["front", "back"]

    def create_listing_group(self, label, search_string, is_img=False, is_refined=False, is_wide=False, is_sold=False):
        return ListingGroup.create(search_result=self, label=label, search_string=search_string, is_img=is_img, is_refined=is_refined, is_wide=is_wide, is_sold=is_sold)
    
    def get_listing_group(self, label):
        try:
            return self.listing_groups.get(label=label)
        except ListingGroup.DoesNotExist:
            return None

    
    def get_crop_params(self, card_id=None):
        if card_id == self.parent_card.reverse_id:
            return self.reverse_crop_params
        else:
            return self.front_crop_params
        
    def save(self, *args, **kwargs):
        print("saving csr")
        if not self.title_to_be_is_manual:
            self.title_to_be = self.build_title()

        filter_terms = self.filter_terms or "" if self.filter_terms != "-" else ""
        if not self.sold_search_string_is_manual:
            self.sold_search_string = str(self.build_title(shorter=True))+" "+filter_terms
        
        if not self.text_search_string_is_manual:
            self.text_search_string = str(self.build_title(shorter=True))+" "+filter_terms

        self.overall_status = min([self.refinement_status, self.pricing_status, self.id_status], key=lambda s: StatusBase.get_id(s))
        
        #super.ugly
        super().save(*args, **kwargs)
        self.aggregate_pricing_data()


        self.sport = ""
        self.league = ""

        #if self.attribute_flags:
            #print(self.attributes)
            #print(self.attribute_flags)
            #self.features = " | ".join(key for key in self.attribute_flags.keys())
            #print(self.features)
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
        elif key == "required_or_excluded":
            return "required_or_excluded"
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
    
    def aggregate_pricing_data(self):
        
        listing_group = self.get_listing_group("sold refined")
        if listing_group and not listing_group.listings.exists():
            listing_group = self.get_listing_group("sold")
        self.ebay_msrp = listing_group.max_price if listing_group else 0.0
            
        '''list_prices = [listing.ebay_price for listing in self.id_listings.all()]
        if len(list_prices) > 0:
            self.ebay_mean_price = statistics.mean(list_prices)
            self.ebay_median_price = statistics.median(list_prices)
            self.ebay_mode_price = statistics.mode(list_prices)
            self.ebay_low_price = min(list_prices)
            self.ebay_high_price = max(list_prices)

        sold_data = sorted([(listing.ebay_price, listing.sold_date) for listing in self.sold_listings.all()], key=lambda x: x[1])
        sold_data = [price for price, _ in sold_data]
        
        if len(sold_data) > 0:
            self.ebay_last_five_avg_sold_price = statistics.mean(sold_data[-5:])
            self.ebay_avg_sold_price = statistics.mean(sold_data)
            self.ebay_last_sold_price = sold_data[-1]
            self.ebay_low_sold_price = min(sold_data)
            self.ebay_high_sold_price = max(sold_data)'''


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
                    aggregate[token.field_key][token.primary_value] += 1
                    self.add_token_link(CardSearchResult.stupid_map(token.field_key), token.primary_value, select=False)
                else:
                    print("no primary token:", token)

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

        threshold = max(1, int(total * 0.10))  # 10% threshold, minimum of 1

        for field_key, counter in aggregate.items():
            field_name = self.stupid_map(field_key)

            if hasattr(self, field_name):
                field = self._meta.get_field(field_name)

                if field_name in self.text_fields:
                    final_value = ", ".join(x for x in counter.keys())

                elif field_name in self.checkbox_fields:
                    final_value = {
                        key[0]: True
                        for key in counter.items()
                        if key[1] >= threshold
                    }

                    if "1st" in final_value:
                        final_value["First"] = final_value["1st"]
                        del final_value["1st"]

                    field_name = "attribute_flags"  # TODO: remove hardcode

                else:
                    
                    most_common = counter.most_common(1)
                    if most_common and (most_common[0][1]/total) >= .1:
                        final_value = most_common[0][0]
                    else:
                        final_value = ""

                self.set_ovr_attribute(field_name, final_value, False)

        
        self.set_ovr_attribute("title_to_be", self.build_title(), False)
        self.save()
        #print("Final collapsed tokens:", self.collapsed_tokens)
        return summary
    
    def clean_text(self, text):
        if text:
            return (
                text.replace('\\', '')      # remove backslashes
                    .replace('`', '')       # remove backticks
                    .replace('"', "")      # replace double quotes with single quotes
                    .replace("'", "")      # replace double quotes with single quotes
                    .replace('\n', ' ')     # flatten newlines
                    .replace('/', '-')     # flatten newlines
                    .replace('(', '_')     # flatten newlines.strip()
                    .replace(')', '_')     # flatten newlines
                    .replace('\t', ' ')     # flatten newlines
                    .strip()
            )
        else: return text

    def update_fields(self, all_field_data):
        #print("afd", all_field_data)
        for field_name, field_value in all_field_data.items():
            #print(field_name)
            if field_name in ['csrfmiddlewaretoken', 'new_field', 'new_value', 'csrId']:
                continue
            
            #check for compound names (checkbox groups, etc)
            if hasattr(self, field_name) or hasattr(self, field_name[:field_name.find('.')]):
                print("has attr", field_name, field_value, self.overrideable_fields)
            
                if field_name in self.overrideable_fields:    
                    print("over")
                    #print(field_name, field_value, all_field_data[f"{field_name}_is_manual"])                
                    is_manual = all_field_data.get(f"{field_name}_is_manual", True)
                    self.set_ovr_attribute(field_name, field_value, is_manual, all_field_data)
                elif field_name.find('.') > 0:#checkbox groups
                    group_name, field_name = field_name.split('.')                     
                    #print(group_name, field_name)
                    #TODO: need to make this more generic to handle additional checkhbox fields
                    if group_name == 'attributes':
                        if field_name == "1st":
                            field_name = "First"
                        print(self.attribute_flags)
                        print(field_name, type(field_value), field_value)
                        #if field_name in self.attribute_flags:
                        if isinstance(field_value, str):
                            self.attribute_flags[field_name] = (field_value.lower() == 'true')
                        else:
                            self.attribute_flags[field_name] = field_value

                else:
                    print("setting: ", field_name, field_value)
                    setattr(self, field_name, field_value)
            elif hasattr(self.parent_card, field_name):
                setattr(self.parent_card, field_name, field_value)
            else:
                print("still fucking oopsie:", field_name)
        print("done")
        self.save()
        print("done2")
        self.parent_card.save()
        print("done3")

    def clear_listings(self):
        self.listings.all().delete()

    @classmethod
    def create_empty(cls, pcard):
        print(f"Create new CSR for card {pcard.id}")
        csr = CardSearchResult(parent_card = pcard)
        csr.front_crop_params = CropParams.clone(pcard.cropped_image.crop_params.last())
        csr.reverse_crop_params = CropParams.clone(pcard.cropped_reverse.crop_params.last())        
        csr.create_listing_group("id", "", is_img=True)

        csr.response_count = 0
        csr.save()
        return csr   
    
    #matches map is keyword_string --> (listing variable, [listings])
    def update_listings(self, matches_map, is_refined=False):
        #print("UP", matches_map)
        results = []
        for keywords in matches_map:
            #print(matches_map[keywords])
            listing_group, listings = matches_map[keywords]
            if len(listing_group.listings.all()) > 0:
                listing_group.listings.all().delete()

            results = [ProductListing.from_search_results(item, self, tokenize=False) for item in listings]
            listing_group.listings.set(results)
            listing_group.save()

            #self.aggregate_pricing_info()
        #print("sold:", sold_listings)
        self.save()

    @classmethod
    def from_search_results(cls, pcard, items=None, tokenize=True, all_fields={}, csr=None, id_listings=False):
        if not csr:
            csr = cls.create_empty(pcard)
        elif id_listings:      
            csr.create_listing_group("id", "", is_img=True)#in case we have a legacy CSR
            csr.get_listing_group("id").listings.all().delete()

        listing_set = []
        #print("locked words: ", all_fields)
        if items and len(items) > 0:
            for idx, item in enumerate(items, 1):
                listing = ProductListing.from_search_results(item, csr, tokenize)
                if listing:
                    listing_set.append(listing)

                if id_listings:
                    listing.listing_group = csr.get_listing_group("id")
                    listing.save()

                        
            csr.response_count = len(listing_set)
            #print("attribs:", csr.attribute_flags)

            #csr.aggregate_pricing_info()

            if tokenize:
                #must pass the listings here to preserve the in memory attributes
                csr.collapsed_tokens = csr.collapse_token_maps(listing_set)

        csr.save()
        return csr
        
    def build_title(self, fields=None, shorter=False, shortest=False, condition_sensitive=False):
        #print("fields:", fields)
        #print("shorter", shorter)
        if shortest:
            title_parts = [
                self.display_value("year"),
                self.display_value("brand"),
                self.display_value("subset")  if self.display_value("subset") != " " else None,
                (self.display_value("full_name") or "").strip().split()[1] if len((self.display_value("full_name") or "").strip().split()) > 1 else None,
                self.display_value("condition") if condition_sensitive else None
            ]
        elif shorter:
            title_parts = [
                self.display_value("year"),
                self.display_value("brand"),
                self.display_value("subset")  if self.display_value("subset") != " " else None,
                self.display_value("full_name"),
                f"#{self.display_value('card_number')}" if self.display_value("card_number") else None,
                self.display_value("condition") if condition_sensitive else None
            ]
        else:
            title_parts = [
                self.display_value("year"),
                self.display_value("brand"),
                self.display_value("subset")  if self.display_value("subset") != " " else None,
                self.display_value("full_name"),
                self.display_value("card_name"),
                "1st" if len(self.attribute_flags) > 0 and self.attribute_flags.get("1st") else None,
                "RC" if len(self.attribute_flags) > 0 and self.attribute_flags.get("RC") else None,
                "HOF" if len(self.attribute_flags) > 0 and self.attribute_flags.get("HOF") else None,
                "Auto" if len(self.attribute_flags) > 0 and self.attribute_flags.get("Auto") else None,
                self.display_value("parallel") if self.display_value("parallel") != " " else None,
                self.display_value("serial_number") if self.display_value("serial_number") != "-" else None,
                f"#{self.display_value('card_number')}" if self.display_value("card_number") else None,
                self.display_value("city"),
                self.display_value("team"),
                self.display_value("condition") if condition_sensitive else None,
                "Oddball" if len(self.attribute_flags) > 0 and self.attribute_flags.get("Oddball") else None
            ]
        title = " ".join(part.strip() for part in title_parts if part and part.strip())
        print("titles:", title)
        return title

    #TODO:these buildable fields should be configurable
    @property
    def full_set(self):
        year = self.display_value("year")
        brand = self.display_value("brand")
        subset = self.display_value("subset")
        
        subset = "" if subset == "-" else subset
        print (f"build_full_set: {year} {brand} {subset}")
        return f"{year} {brand} {subset}".strip()
    
    #TODO:these buildable fields should be configurable
    @property
    def full_team(self):
        city = self.display_value("city")
        team = self.display_value("team")
        print (f"build_full_team: {city} {team}")
        return f"{city} {team}"
    
    #TODO:Too many saves
    def build_sku(self):
        full_set = self.full_set
        sku = f"{full_set} {self.display_value('full_name')}".replace(" ", "-").upper()
        return sku
    
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
        if filled_template["product"]["aspects"]["Card Name"] == "":
            filled_template["product"]["aspects"]["Card Name"] == []
            
        filled_template["sku"] = sku
        filled_template["product"]["aspects"]["Autographed"] = "Yes" if "Auto" in self.attributes else "No"
        filled_template["condition"] = "USED_VERY_GOOD"

        #if self.condition
        print("condition:", self.condition)
        condition = self.condition or "NM"#blank condition = NM
        condition_token = Condition.objects.get(raw_value=condition)
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
        filled_template["product"]["aspects"] = {
            k: [v] for k, v in filled_template["product"]["aspects"].items() if v
        }

        
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
        #print(self)
        listing_set = self.listings.all()
        for listing in listing_set:
            #title = listing.title
            #print("title ID: ", listing.title.id)
            listing.title.tokenize(applied_settings)
            #print("After tokenize:", listing.title.serial_number_tokens)

        self.collapse_token_maps(listing_set)
        self.aggregate_pricing_info()


#vanguard confirmation number:w54e075777

class ListingGroup(models.Model):
    search_result = models.ForeignKey(CardSearchResult, on_delete=models.CASCADE, related_name="listing_groups")
    
    is_sold = models.BooleanField(default=False)
    is_refined = models.BooleanField(default=False)
    is_wide = models.BooleanField(default=False)
    is_img = models.BooleanField(default=False)
    label = models.CharField(max_length=100, blank=True, null=True)  # e.g. "Sold Refined Wide"
    search_string = models.CharField(max_length=255, blank=True, null=True)

    color = models.CharField(max_length=50, default="rgba(204, 153, 0, 0.8)")
    border_width = models.IntegerField(default=2)
    line_style = models.CharField(max_length=10, choices=[("solid", "Solid"), ("dotted", "Dotted")], default="solid")
    display = models.BooleanField(default=False)

    min_price = models.FloatField(default=0.0)
    max_price = models.FloatField(default=0.0)
    min_date = models.DateField(null=True)
    max_date = models.DateField(null=True)

    class Meta:
        unique_together = ("search_result", "is_sold", "is_refined", "is_wide", "is_img")

    @classmethod
    def create(cls, search_result, label, search_string, is_img=False, is_refined=False, is_wide=False, is_sold=False):
        search_result.save()
        group, _ = search_result.listing_groups.get_or_create(search_result=search_result, is_img=is_img, is_refined=is_refined, is_wide=is_wide, is_sold=is_sold)
        group.label = label
        group.search_string = search_string
        
        # Base color
        group.color = "rgba(60, 179, 113, 0.8)" if is_sold else "rgba(204, 153, 0, 0.3)"  # green vs dark yellow
        group.display = not is_wide and not is_img
        # Border width
        group.border_width = 3 if is_refined else 1

        # Line style
        group.line_style = "dotted" if is_wide else "solid"

        group.save()
        return group

    def save(self, *args, **kwargs):
        if self.pk and self.listings.exists():
            listing_list = self.listings.all()
            self.min_price = min(listing.ebay_price for listing in listing_list)
            self.max_price = max(listing.ebay_price for listing in listing_list)

            min_datetime = min(listing.display_date for listing in listing_list)
            self.min_date = datetime.fromisoformat(min_datetime.replace("Z", "+00:00")).date()

            max_datetime = max(listing.display_date for listing in listing_list)
            self.max_date = datetime.fromisoformat(max_datetime.replace("Z", "+00:00")).date()

        super().save(*args, **kwargs)

    def serialize_listings(self):
        return [
            [
                listing.ebay_price,
                listing.title.title if listing.title else "",
                listing.thumb_url,
                listing.display_date
            ]
            for listing in self.listings.filter(
                ebay_price__isnull=False
            )
        ]


    def __str__(self):
        return self.label or ""

class ProductListing(models.Model):

    item_id = models.CharField(max_length=100, blank=True)
    listing_date = models.DateTimeField(blank=False, null=True)
    sold_date = models.DateTimeField(blank=False, null=True)
    img_url = models.CharField(max_length=250, null=True, blank=True)
    thumb_url = models.CharField(max_length=250, blank=False)    #title is declared below
    ebay_price = models.FloatField(default=0.0)
    format = models.CharField(max_length=100, blank=True)
    qty = models.IntegerField(default=1)
    
    #legacy
    search_result = models.ForeignKey(CardSearchResult, on_delete=models.CASCADE, default=1, related_name="listings")    
    listing_group = models.ForeignKey(ListingGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="listings")

    @property
    def display_date(self):
        return self.sold_date.isoformat() if self.sold_date else self.listing_date.isoformat()

    @classmethod
    def from_search_results(cls, item, parent_csr, tokenize=True):
        listing = cls()
        listing.item_id = item.get("itemId", "N/A")
        listing.listing_date = item.get("itemCreationDate", None)
        sold_date = item.get("sold_date", None)
        if sold_date:
            listing.sold_date = datetime.strptime(sold_date, "%b %d, %Y").strftime("%Y-%m-%d %H:%M:%S")
        
        img_url = item.get("itemWebUrl", "No thumbnail")
        if not img_url:
            listing.img_url=""
        elif img_url[:4] == "http":
            listing.img_url = img_url
        else:
            listing.img_url = "http:"+img_url

        listing.thumb_url = item.get("thumbnailImages", [{}])[0].get("imageUrl", listing.img_url)
        price = item.get("price", [{}])
        if isinstance(price, str):
            listing.ebay_price = price.replace('$', '').replace(',', '')
        else:
            listing.ebay_price = price.get("value","0")

        listing.format = item.get("format", "N/A")
        listing.qty = item.get("qty", "1")
        listing.search_result = parent_csr
        listing.save()
        listing.title = ListingTitle.objects.create(title=item.get("title", "No title"), parent_listing=listing)
        listing.save()        
        #TODO:ultimately this will need to be updated to handle multiple settings objects
        if tokenize:
            listing.title.tokenize(Settings.get_default())

        return listing


class ListingTitle(models.Model):
    title = models.CharField(max_length=100, blank=True, null=True)
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


    def get_all_tokens(self):
        token_fields = [
            "brand_tokens",
            "subset_tokens",
            "team_tokens",
            "city_tokens",
            "known_name_tokens",
            "card_attribute_tokens",
            "condition_tokens",
            "parallel_tokens",
            "card_name_tokens",
        ]

        all_tokens = []
        for field in token_fields:
            manager = getattr(self, field, None)
            if manager:
                all_tokens.extend(manager.all())

        return all_tokens



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
        #print("New tokens: ", self.season_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Brand.match_extract(temp_title, tokens, "brands", applied_settings)
        self.brand_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Parallel.match_extract(temp_title, tokens, "parallel", applied_settings)
        self.parallel_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = KnownName.match_extract(temp_title, tokens, "names", applied_settings)
        self.known_name_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = City.match_extract(temp_title, tokens, "cities", applied_settings)
        self.city_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Team.match_extract(temp_title, tokens, "teams", applied_settings)
        self.team_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Condition.match_extract(temp_title, tokens, "condition", applied_settings, return_first_match=True)
        self.condition_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Subset.match_extract(temp_title, tokens, "subsets", applied_settings)
        self.subset_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = CardName.match_extract(temp_title, tokens, "card_name", applied_settings, return_first_match=True)
        self.card_name_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = CardAttribute.match_extract(temp_title, tokens, "attribs", applied_settings, return_first_match=False)
        self.card_attribute_tokens.set(new_tokens)
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        #I think these can go anywhere without conflicting with anythign except each other
        temp_title, tokens, self.card_number_tokens = CardNumber.match_extract(temp_title, tokens, "cardnr", applied_settings, return_first_match=False)
        
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, self.serial_number_tokens = SerialNumber.match_extract(temp_title, tokens, "serial", applied_settings, return_first_match=False)
        
        #print("New tokens: ", new_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)

        unknown_tokens = re.findall(r'\b#?[a-z0-9]{2,}(?:-[a-z0-9]{2,})?\b', temp_title.lower())
        unknown_tokens = [self.normalize_word(t) for t in unknown_tokens if len(t) >= 3]
        self.unknown_tokens = unknown_tokens
        #print ("hi", self.id)
        #self.tokens = tokens

        self.save()
        
        #print(self.id)
        #print ("end tokenize: ", self.serial_number_tokens)
        #print ("end tokenize: ", self.card_number_tokens)
        #print ("end tokenize: ", self.season_tokens)

    def __str__(self):
        return self.title or ""

