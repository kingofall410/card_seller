from django.db import models
from django.db import IntegrityError, DatabaseError
#from django.db.models import Avg
from django.utils import timezone
#from scipy.stats import trim_mean
import re, statistics
from core.models.Cropping import CropParams
from core.models.Status import *
from core.models.Group import *
#from core.models.ListingGroup import *
from services.models.models import Brand, Subset, Team, City, KnownName, CardAttribute, Settings, CardNumber, Season, SerialNumber, Condition, Parallel, CardName
#from collections import defaultdict, Counter
#from services import settings_management as app_settings
from datetime import datetime
from dateutil.relativedelta import relativedelta
import traceback
#from itertools import product, combinations

class ListingGroup(models.Model):
    search_result = models.ForeignKey('core.CardSearchResult', on_delete=models.CASCADE, related_name="listing_groups")
    modification_date = models.DateTimeField(auto_now_add=True)

    is_sold = models.BooleanField(default=False, blank=True, null=True)
    is_refined = models.BooleanField(default=False, blank=True, null=True)
    is_wide = models.BooleanField(default=False, blank=True, null=True)
    is_img = models.BooleanField(default=False, blank=True, null=True)
    label = models.CharField(max_length=500, blank=True, null=True)  # e.g. "Sold Refined Wide"
    search_string = models.CharField(max_length=500, blank=True, null=True)
    filter_terms = models.CharField(max_length=250, blank=True, null=True)
    id_string = models.CharField(max_length=250, blank=True, null=True)

    color = models.CharField(max_length=100, default="rgba(204, 153, 0, 0.8)")
    border_width = models.IntegerField(default=2)
    line_style = models.CharField(max_length=10, choices=[("solid", "Solid"), ("dotted", "Dotted")], default="solid")
    display = models.BooleanField(default=False, blank=True, null=True)

    min_price = models.FloatField(default=0.0)
    max_price = models.FloatField(default=0.0)
    avg_price = models.FloatField(default=0.0)
    price_spread = models.FloatField(default=0.0)
    recent_avg_price = models.FloatField(default=0.0)
    min_date = models.DateField(null=True)
    max_date = models.DateField(null=True)
    
    recent_date = models.DateField(null=True)
    
    trend_recent = models.FloatField(default=0.0)
    trend_overall = models.FloatField(default=0.0)
    trend_unfiltered = models.FloatField(default=0.0)

    overall_start_price = models.FloatField(default=0.0)
    overall_end_price = models.FloatField(default=0.0)
    unfiltered_start_price = models.FloatField(default=0.0)
    unfiltered_end_price = models.FloatField(default=0.0)
    
    recent_trend_start_price = models.FloatField(default=0.0)

    class Meta:
        unique_together = ("search_result", "label")
    
    def get_search_string(self, id_string=None):
        if id_string:
            self.id_string = id_string
            self.save()
        ss = " ".join([id_string, (self.filter_terms or ""), (self.search_result.display_filter_terms or "")])
        return " ".join(ss.split())


    

    @property
    def modified_avg(self):
        return 0        


    @property
    def display_state(self):
        return "expanded" if self.label.find("ID") >= 0 else "collapsed" 

    @classmethod
    def create(cls, search_result, label, filter_terms, id_string, is_img=False, is_refined=False, is_wide=False, is_sold=False):
        # 1. Force save the parent and ensure it has an ID
        search_result.save()
        if not search_result.id:
            print("❌ Parent SearchResult has no ID. Cannot create group.")
            return None

        # 2. Use ONLY the absolute unique identifiers to find the record
        # If these match, we update. If not, we create.
        try:
            group, created = cls.objects.get_or_create(
                search_result=search_result,
                label=label,
                # If is_img or is_sold changes a group's identity, keep them here. 
                # If not, move them to defaults.
                is_img=is_img, 
                is_sold=is_sold,
                defaults={'filter_terms': filter_terms, 'id_string': id_string}
            )
        except cls.MultipleObjectsReturned:
            # Emergency backup: if the DB is already messy, grab the last one
            group = cls.objects.filter(search_result=search_result, label=label).last()
            created = False

        # 3. Now set the fields that might have changed
        group.filter_terms = filter_terms
        group.id_string = id_string
        group.is_wide = is_wide
        group.display = "Raw" in label
        group.border_width = 3 if is_refined else 1
        group.line_style = "dotted" if is_wide else "solid"
        group.color = "rgba(60, 179, 113, 0.8)" if is_sold else "rgba(204, 153, 0, 0.3)"

        # 4. The Final Save
        try:
            group.save()
            # If this works, the ID will definitely be there
            print(f"✅ Final Save Success. ID: {group.id}")
            return group
        except Exception as e:
            print(f"❌ THE ACTUAL DB ERROR: {e}")
            # Look closely at this output - it will name the specific field causing the crash
            return None
    @property
    def relevence_filter_bounds(self):
        data = [float(l.ebay_price) for l in self.listings.all()]
        return self.get_relevence_filter_bounds(data)
    
    def get_relevence_filter_bounds(self, data):

        if len(data) < 4:  # Statistical filtering requires a decent sample size
            return -1, 99999

        data.sort()

        # Calculate Quartiles
        q1, _, q3 = statistics.quantiles(data, n=4)
        iqr = q3 - q1
        
        # Define bounds (standard multiplier is 1.5)
        lower_bound = q1 - (1.5 * iqr)
        upper_bound = q3 + (1.5 * iqr)

        return lower_bound, upper_bound

    def filter_outliers(self, data):
        lower_bound, upper_bound = self.get_relevence_filter_bounds(data)
        
        return [x for x in data if lower_bound <= x <= upper_bound]    

    def save(self, *args, **kwargs):
        if self.pk and self.listings.exists():
            # 1. Sort the OBJECTS once. display_date() is a function, so call it in the key.
            listing_list = sorted(self.listings.all(), key=lambda x: x.display_date)
            
            # 2. Extract date strings using the function
            date_strings = [l.display_date for l in listing_list if l.display_date]
            
            if date_strings:
                # Since listing_list is sorted, min is index 0, max is index -1
                min_dt_str = date_strings[0]
                max_dt_str = date_strings[-1]
                
                self.min_date = datetime.fromisoformat(min_dt_str.replace("Z", "+00:00")).date()
                self.max_date = datetime.fromisoformat(max_dt_str.replace("Z", "+00:00")).date()
                
                six_months_ago = self.max_date - relativedelta(months=6)
                self.recent_date = six_months_ago
                total_days = (self.max_date - self.min_date).days or 1

                # 3. Segregate Data while MAINTAINING ORDER
                # We build these from the already-sorted listing_list
                recent_listings = []
                float_prices_all = []
                
                for l in listing_list:
                    if l.ebay_price is not None:
                        price = float(l.ebay_price)
                        float_prices_all.append(price)
                        
                        # Check if this listing is "recent"
                        l_date_str = l.display_date
                        if l_date_str:
                            l_date = datetime.fromisoformat(l_date_str.replace("Z", "+00:00")).date()
                            if l_date >= six_months_ago:
                                recent_listings.append(l)

                # Extract recent prices from the recent_listings (which are still sorted)
                float_prices_recent = [float(l.ebay_price) for l in recent_listings]

                # 4. Filter Outliers (Maintains relative order)
                clean_prices_all = self.filter_outliers(float_prices_all)
                clean_prices_recent = self.filter_outliers(float_prices_recent)

                if clean_prices_all:
                    self.min_price = min(float_prices_all)
                    self.max_price = max(float_prices_all)
                    self.avg_price = sum(float_prices_all) / len(float_prices_all)

                    # --- 1. TREND UNFILTERED (First 5% Avg to Last 5%) ---
                    if len(float_prices_all) >= 2:
                        # 1. Calculate buffer (5% of data)
                        buffer_size = max(1, int(len(float_prices_all) * 0.2))

                        # 2. Start point: Average of the FIRST 5%
                        first_5_percent_avg = sum(float_prices_all[:buffer_size]) / buffer_size

                        # 3. End point: Average of the LAST 5% 
                        # FIXED SLICE: [-buffer_size:] gets the end of the list
                        last_5_percent_avg = sum(float_prices_all[-buffer_size:]) / buffer_size
                        print("bs", buffer_size, first_5_percent_avg, last_5_percent_avg)
                        
                        # 4. Calculate ftrend
                        if first_5_percent_avg > 0:
                            self.trend_overall = ((last_5_percent_avg - first_5_percent_avg) / first_5_percent_avg * 100)
                        else:
                            self.trend_overall = 0

                        # Store the start and end points for JS plotting
                        self.unfiltered_start_price = first_5_percent_avg
                        self.unfiltered_end_price = last_5_percent_avg
                        
                    # --- 1. TREND OVERALL (First 5% Avg to Last 5%) ---
                    if len(clean_prices_all) >= 2:
                        # 1. Calculate buffer (5% of data)
                        buffer_size = max(1, int(len(clean_prices_all) * 0.2))

                        # 2. Start point: Average of the FIRST 5%
                        first_5_percent_avg = sum(clean_prices_all[:buffer_size]) / buffer_size

                        # 3. End point: Average of the LAST 5% 
                        # FIXED SLICE: [-buffer_size:] gets the end of the list
                        last_5_percent_avg = sum(clean_prices_all[-buffer_size:]) / buffer_size
                        print("bs", buffer_size, first_5_percent_avg, last_5_percent_avg)
                        
                        # 4. Calculate ftrend
                        if first_5_percent_avg > 0:
                            self.trend_overall = ((last_5_percent_avg - first_5_percent_avg) / first_5_percent_avg * 100)
                        else:
                            self.trend_overall = 0

                        # Store the start and end points for JS plotting
                        self.overall_start_price = first_5_percent_avg
                        self.overall_end_price = last_5_percent_avg
                        #this will be the RRP
                        self.recent_avg_price = self.overall_end_price

                    # --- 2. TREND RECENT (Branching off the Overall Trend) ---
                    if len(clean_prices_recent) >= 2:
                        # 1. Find the "Overall Trend Value" at the moment the recent period started
                        # We use the index to find how far through the timeline we are
                        total_count = len(clean_prices_all)
                        recent_count = len(clean_prices_recent)
                        progress_ratio = (total_count - recent_count) / total_count if total_count > 0 else 0

                        # The Y-value on the Overall Trend line where the Recent Trend starts
                        self.recent_trend_start_price = self.overall_start_price + (
                            (self.overall_end_price - self.overall_start_price) * progress_ratio
                        )

                        # Recent trend starts at the branch and ends at the actual current average (last 5%)
                        self.trend_recent = ((last_5_percent_avg - self.recent_trend_start_price) / self.recent_trend_start_price * 100) if self.recent_trend_start_price > 0 else 0
                    else:
                        self.trend_recent = 0
                        self.recent_avg_price = self.avg_price

                    # --- VELOCITY ---
                    total_months = total_days / 30.44
                    self.velocity_total = len(listing_list) / total_months if total_months > 0 else len(listing_list)
                    
                    recent_days = (self.max_date - six_months_ago).days
                    recent_months = min(recent_days, total_days) / 30.44
                    self.velocity_recent = len(recent_listings) / recent_months if recent_months > 0 else 0
                else:
                    # Reset values if no clean prices found
                    self.min_price = self.max_price = self.avg_price = 0
                    self.trend_overall = self.trend_recent = self.velocity_total = self.velocity_recent = 0
            
        self.search_string = " ".join(filter(None, [self.id_string, self.filter_terms]))
        super().save(*args, **kwargs)
        self.search_result.update_value()

    def serialize_listings(self):
        if self.label == "graded":
            return []
        return [
            [
                listing.ebay_price,
                listing.title.title if listing.title else "",
                listing.thumb_url,
                listing.display_date,
                listing.id
            ]
            for listing in self.listings.filter(
                ebay_price__isnull=False
            )
        ]


    def __str__(self):
        return self.label or ""
#TODO:needs to be split further into types of listings (ebay, psa, etc) and merged with the mess that CSRs has become
class ProductListing(models.Model):

    item_id = models.CharField(max_length=500, blank=True)
    listing_date = models.DateTimeField(blank=False, null=True)
    sold_date = models.DateTimeField(blank=False, null=True)
    img_url = models.CharField(max_length=250, null=True, blank=True)
    thumb_url = models.CharField(max_length=250, blank=False)    #title is declared below
    ebay_price = models.FloatField(default=0.0)
    format = models.CharField(max_length=500, blank=True)
    qty = models.IntegerField(default=1)
    
    #legacy
    search_result = models.ForeignKey('core.CardSearchResult', on_delete=models.CASCADE, default=1, related_name="listings")    
    listing_group = models.ForeignKey(ListingGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="listings")

    @property
    def display_date(self):
        return self.sold_date.isoformat() if self.sold_date else self.listing_date.isoformat()

    @property
    def pretty_display_date(self):
        return self.sold_date if self.sold_date else self.listing_date

    @classmethod
    def from_graded_card_record(cls, record, parent_csr, tokenize=True):
        listing = cls(search_result=parent_csr)
        listing.item_id = record.get("cert_number", "N/A")
        
        #a lot of this actually happens on the csr itself since we have hard data
        #parent_csr.derive_grade_condition(record.get("grade", None))
        #parent_csr.derive_brand_subset(record.get("set_name", None))
        #parent_csr.update_fields(record)
        
        return listing

    @classmethod
    def from_search_results(cls, item, parent_csr, tokenize=True):
        
        listing = cls()
        listing.item_id = item.get("itemId", "N/A")
        listing.listing_date = item.get("itemCreationDate", None)
        sold_date_str = item.get("sold_date", None)
        if sold_date_str:
            # 1. Parse the string into a naive datetime object
            naive_dt = datetime.strptime(sold_date_str, "%b %d, %Y")
            
            # 2. Make it "Aware" (adds the TZ info from your settings.py)
            aware_dt = timezone.make_aware(naive_dt)
            
            # 3. Assign the aware object directly to the model field
            listing.sold_date = aware_dt
        
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
        listing.qty = item.get("qty", "1").replace(",","")
        listing.search_result = parent_csr
        listing.save()
        listing.title = ListingTitle.objects.create(title=item.get("title", "No title"), parent_listing=listing)
        listing.save()        
        #TODO:ultimately this will need to be updated to handle multiple settings objects
        if tokenize:
            listing.title.tokenize(Settings.get_default())

        return listing


class ListingTitle(models.Model):
    title = models.CharField(max_length=500, blank=True, null=True)
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
        #print(self.id)
        #this logic relies on the fact that the "key" must match something defined by reading in settings.  Thus, don't change these
        temp_title, tokens, self.season_tokens = Season.match_extract(self.title, tokens, "year", applied_settings, return_first_match=False)
        print("pre brand: New tokens: ", self.season_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Brand.match_extract(temp_title, tokens, "brands", applied_settings)
        self.brand_tokens.set(new_tokens)
        print("post brand: New tokens: ", new_tokens)
        print("old tokens: ", tokens)
        print("Remaining Title: ", temp_title)
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
