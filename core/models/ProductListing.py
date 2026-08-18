from django.db import models
from core.models.ListingGroup import ListingGroup
from services.models.models import Brand, Subset, Team, City, KnownName, CardAttribute, Settings, CardNumber, Season, SerialNumber, Condition, Parallel, CardName
from datetime import datetime
from django.utils import timezone

#TODO:needs to be split further into types of listings (ebay, psa, etc) and merged with the mess that CSRs has become
class ProductListing(models.Model):

    item_id = models.CharField(max_length=500, blank=True)
    listing_date = models.DateTimeField(blank=False, null=True)
    sold_date = models.DateTimeField(blank=False, null=True)
    img_url = models.CharField(max_length=1500, null=True, blank=True)
    thumb_url = models.CharField(max_length=500, blank=False)    #title is declared below
    ebay_price = models.FloatField(default=0.0)
    format = models.CharField(max_length=500, blank=True)
    qty = models.IntegerField(default=1)
    bids = models.IntegerField(default=0)
    
    #legacy
    search_result = models.ForeignKey('core.CardSearchResult', on_delete=models.CASCADE, null=True, related_name="listings")    
    listing_group = models.ForeignKey(ListingGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="listings")
    as_recent_listing = models.ForeignKey(ListingGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="recent_listings_rel")

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
    def from_facebook_results(cls, item, tokenize=False):
        """
        Constructs and saves a database Listing instance from a scraped 
        Facebook Marketplace item dictionary.
        
        :param item: Dictionary containing scraped data (title, price, url, local_image_path, etc.)
        :param parent_csr: The parent search result context (active_search_results equivalent)
        :param tokenize: Boolean flag to trigger title tokenization
        """
        listing = cls()
        print(item)
        # 1. Extract and Clean Listing ID from the Facebook URL
        url = item.get("url", "")
        id_match = re.search(r"/item/(\d+)", url)
        listing.item_id = id_match.group(1) if id_match else "FB_N/A"
        
        # 2. Assign Timezone-Aware Dates (defaults to now as FB doesn't give a direct public timestamp easily)
        # If your scraper extracts a creation timestamp, parse it similarly to the sold_date logic.
        listing.listing_date = timezone.now()
        listing.sold_date = None  # Marketplace items usually don't have historical "sold" dates scraping from live feed
        
        # 3. Handle Images (use the downloaded local image path if available, fallback to the external CDN URL)
        local_path = item.get("local_image_path")
        external_url = item.get("image_url", "")
        
        # Fallback assignment
        listing.img_url = local_path if local_path else external_url
        listing.thumb_url = external_url
        
        # 4. Clean and Parse Price (extract digits and decimals from strings like "$123.45")
        raw_price = item.get("price", "0")
        # Strip currency symbols and commas to leave a clean float-compatible string
        clean_price = re.sub(r"[^\d.]", "", raw_price)
        listing.ebay_price = clean_price if clean_price else "0"
        
        # 5. Default Attributes for FB's structural differences
        listing.format = "Classified/Local"  # FB Marketplace default style
        listing.bids = "0"
        listing.qty = "1"
        
        # 6. Save the Base Listing
        listing.save()
        
        # 7. Create Nested Title Object
        listing.title = ListingTitle.objects.create(
            title=item.get("title", "No Title"), 
            parent_listing=listing
        )
        listing.save()
        
        # 8. Tokenize Title
        if tokenize:
            listing.title.tokenize(Settings.get_default())
            
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
        #print("item", item)
        listing.thumb_url = item.get("thumbnailImages", [{}])[0].get("imageUrl", listing.img_url)
        listing.img_url = listing.thumb_url
        price = item.get("price", [{}])
        if isinstance(price, str):
            listing.ebay_price = price.replace('$', '').replace(',', '')
        else:
            listing.ebay_price = price.get("value","0")

        listing.format = item.get("format", None)
        listing.bids = item.get("bids", "0").replace("-","0")
        if not listing.format:
            listing.format = item.get("buyingOptions", [""])[0]
        listing.qty = item.get("qty", "1").replace(",","")
        listing.search_result = parent_csr
        #print(listing.item_id)
        #print(listing.thumb_url)
        #print(listing.img_url)
        #print(listing.format)
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
        #print("pre brand: New tokens: ", self.season_tokens)
        #print("old tokens: ", tokens)
        #print("Remaining Title: ", temp_title)
        temp_title, tokens, new_tokens = Brand.match_extract(temp_title, tokens, "brands", applied_settings)
        self.brand_tokens.set(new_tokens)
        #print("post brand: New tokens: ", new_tokens)
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
