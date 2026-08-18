from django.db import models
from django.db import IntegrityError, DatabaseError
#from django.db.models import Avg
from django.utils import timezone
#from scipy.stats import trim_mean
import re, statistics
from core.models.Cropping import CropParams
from core.models.Status import *
from core.models.ProductGroup import *
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
    modification_date = models.DateTimeField(auto_now=True)

    is_sold = models.BooleanField(default=False, blank=True, null=True)
    is_refined = models.BooleanField(default=False, blank=True, null=True)
    is_wide = models.BooleanField(default=False, blank=True, null=True)
    is_img = models.BooleanField(default=False, blank=True, null=True)
    label = models.CharField(max_length=500, blank=True, null=True)  # e.g. "Sold Refined Wide"
    search_string = models.CharField(max_length=500, blank=True, null=True)
    filter_terms = models.CharField(max_length=500, blank=True, null=True)
    id_string = models.CharField(max_length=500, blank=True, null=True)

    color = models.CharField(max_length=100, default="rgba(204, 153, 0, 0.8)")
    border_width = models.IntegerField(default=2)
    line_style = models.CharField(max_length=10, choices=[("solid", "Solid"), ("dotted", "Dotted")], default="solid")
    display = models.BooleanField(default=False, blank=True, null=True)

    min_price = models.FloatField(default=0.0)
    max_price = models.FloatField(default=0.0)
    last_5_min_price = models.FloatField(default=0.0)
    last_5_max_price = models.FloatField(default=0.0)
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
    clusters = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ("search_result", "label")
    
    @property 
    def force_search_string(self):
        return self.get_search_string(self.search_result.build_search_string())

    def get_search_string(self, id_string=""):
        if id_string:
            self.id_string = id_string
            self.save()
        print(self.search_result.display_filter_terms, self.search_result.display_parallel_filter_terms)
        all_terms = (self.search_result.display_filter_terms.split() if self.search_result.display_filter_terms else []) \
            + (self.search_result.display_parallel_filter_terms.split() if self.search_result.display_parallel_filter_terms else []) \
            + (self.filter_terms.split() if self.filter_terms else [])
        
        id_string_lower = id_string.lower()

        filter_terms = [x.lower() if "(" not in x else x for x in all_terms
            if x and not (x.lower().startswith("-") and x.lower()[1:] in id_string_lower)
        ]
    
        print("FILTER TERMS: ", filter_terms)
        
        ss = " ".join([id_string] + filter_terms)
        search_string_all_tokens = [token.lower() for token in ss.split()]
        deconflicted_search_tokens = [x for x in search_string_all_tokens if x[0] != "-" or x[1:] in search_string_all_tokens]
        self.search_string = " ".join(ss.split())
        print("deconflicted final search string:", self.search_string)
        return self.search_string

    @property
    def is_graded(self):
        return self.label.find("PSA") >= 0        

    @property
    def modified_avg(self):
        return 0        

    def build_clusters(self, clean_prices, distance_threshold=None):
        """
        Calculates cluster center (price) and size (% weight of total listings) 
        from the clean prices list, and caches the dict array on self.clusters.
        """
        if not clean_prices:
            self.clusters = []
            return

        # 1. Elements must be sorted for single-linkage clustering
        sorted_prices = sorted(clean_prices)
        total_listings_count = len(sorted_prices)  # Base denominator for size %
        cluster_groups = []
        
        if total_listings_count < 2:
            cluster_groups.append(sorted_prices)
        else:
            if distance_threshold is None:
                try:
                    stdev = statistics.stdev(sorted_prices)
                    distance_threshold = max(1.0, stdev * 0.25)
                except statistics.StatisticsError:
                    distance_threshold = 1.0

            current_cluster = [sorted_prices[0]]

            for price in sorted_prices[1:]:
                if price - current_cluster[-1] <= distance_threshold:
                    current_cluster.append(price)
                else:
                    cluster_groups.append(current_cluster)
                    current_cluster = [price]
            
            if current_cluster:
                cluster_groups.append(current_cluster)

        # 2. Compute payload metrics with size as a percentage
        cluster_payload = []
        for group in cluster_groups:
            center_price = statistics.median(group)
            
            # Calculate what percentage of total clean sales belong to this cluster
            size_percentage = (len(group) / total_listings_count) * 100.0
            
            cluster_payload.append({
                "center": round(center_price, 2),
                "size": round(size_percentage, 2)  # Represented as a clean percentage (e.g., 25.00)
            })

        cluster_payload.sort(key=lambda x: x["size"], reverse=True)
        self.clusters = cluster_payload

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

        data = sorted(data)

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
        
        print("LG save ", self.id)
        if self.pk and self.listings.exists():
            # 1. Sort the OBJECTS once. display_date() is a function, so call it in the key.
            listing_list = sorted(self.listings.all(), key=lambda x: x.display_date)
            
            # 2. Extract date strings using the function
            date_strings = [l.display_date for l in listing_list if l.display_date]
            #print(date_strings)
            if date_strings:
                # Since listing_list is sorted, min is index 0, max is index -1
                min_dt_str = date_strings[0]
                max_dt_str = date_strings[-1]
                
                self.min_date = datetime.fromisoformat(min_dt_str.replace("Z", "+00:00")).date()
                self.max_date = datetime.fromisoformat(max_dt_str.replace("Z", "+00:00")).date()
                
                six_months_ago = self.max_date - relativedelta(months=6)
                self.recent_date = max(self.min_date, six_months_ago)
                total_days = (self.max_date - self.min_date).days or 1

                # 3. Segregate Data while MAINTAINING ORDER
                # We build these from the already-sorted listing_list
                recent_listings = []
                float_prices_all = []
                
                for l in listing_list:
                    if l.ebay_price is not None and (l.format != 'Auction' or l.bids > 1):
                        price = float(l.ebay_price)
                        float_prices_all.append(price)
                        
                        # Check if this listing is "recent"
                        l_date_str = l.display_date
                        if l_date_str:
                            l_date = datetime.fromisoformat(l_date_str.replace("Z", "+00:00")).date()
                            if l_date >= self.recent_date:
                                recent_listings.append(l)
                                
                self.recent_listings_rel.set(recent_listings)
                # Extract recent prices from the recent_listings (which are still sorted)
                float_prices_recent = [float(l.ebay_price) for l in recent_listings]
                #print("float", float_prices_all)
                # 4. Filter Outliers (Maintains relative order)
                clean_prices_all = self.filter_outliers(float_prices_all)
                clean_prices_recent = self.filter_outliers(float_prices_recent)
                
                #print("clean", clean_prices_all)
                if clean_prices_all:
                    self.min_price = min(float_prices_all)
                    self.max_price = max(float_prices_all)
                    self.avg_price = sum(float_prices_all) / len(float_prices_all)

                    self.build_clusters(clean_prices_all)

                    # --- 1. TREND UNFILTERED (First 5% Avg to Last 5%) ---
                    if len(float_prices_all) >= 2:
                        # 1. Calculate buffer (5% of data)
                        buffer_size = max(1, int(len(float_prices_all) * 0.2))

                        # 2. Start point: Average of the FIRST 5%
                        first_5_percent_avg = sum(float_prices_all[:buffer_size]) / buffer_size

                        # 3. End point: Average of the LAST 5% 
                        # FIXED SLICE: [-buffer_size:] gets the end of the list
                        last_5_percent_avg = sum(float_prices_all[-buffer_size:]) / buffer_size
                        print("buffer info", buffer_size, first_5_percent_avg, last_5_percent_avg)
                        
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
                        last_5_pct = clean_prices_all[-buffer_size:]
                        last_5_percent_avg = sum(last_5_pct) / buffer_size
                        self.last_5_min_price = min(last_5_pct)
                        self.last_5_max_price = max(last_5_pct)
                        
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
        self.search_result.update_value()
        super().save(*args, **kwargs)

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
