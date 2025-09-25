from django.db import models
from django.contrib.auth.models import User
from dataclasses import dataclass
import re
from django.db.models import Q
from urllib.parse import unquote

class Settings(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1, related_name="active_settings")    
    nr_returned_listings = models.IntegerField(default=10)
    nr_collection_page_items = models.IntegerField(default=10)
    field_pct_threshold = models.FloatField(default=0.3)
    
    #TODO: this should be broken into separate classes, especially now I need one for sandbox
    ebay_user_auth_code = models.CharField(blank=True)
    ebay_refresh_token = models.CharField(blank=True)
    ebay_refresh_token_expiration = models.FloatField(default=0.0)
    ebay_access_token = models.CharField(blank=True)
    ebay_access_token_expiration = models.FloatField(default=0.0)
    ebay_user_auth_consent = models.CharField(max_length=250, blank=True, null=True)
    ebay_auth_code_unescaped = models.CharField(blank=True)

    nr_std_devs = models.FloatField(default=2.0)

    def load_from_files(self, brand_path=None, team_path=None, name_path=None):
        if brand_path:
            with open(brand_path, "r") as f:
                self.brand_set = {line.strip() for line in f if line.strip()}

        if team_path:
            with open(team_path, "r") as f:
                self.team_set = {line.strip() for line in f if line.strip()}

        if name_path:
            import json
            with open(name_path, "r") as f:
                self.name_mapping = json.load(f)

    '''def __repr__(self):
        return (
            f"SettingsObject(\n"
            f"  Brands: {len(self.brands)} items,\n"
            f"  Teams: {len(self.teams)} items,\n"
            f"  Name Mappings: {len(self.name_mapping)} keys\n"
            f")"
        )'''
    
    @classmethod
    def get_default(cls):
        return Settings.objects.first()

class SettingsToken(models.Model):
    field_key = models.CharField(max_length=100, blank=False, default="None") 
    raw_value = models.CharField(max_length=100, blank=False, default="")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, default=1)
    match_source_formatting = models.BooleanField(default=False)
    primary_attrib = models.CharField(max_length=100, blank=True, default="")#TODO: remove in favor of primary_token
    primary_token = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name="alias_tokens")
    disabled_date = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.raw_value}"
    
    '''def __eq__(self, value):
        if isinstance(value, str):
            return any(item.raw_value == value for item in self.get)
        elif isinstance(value, SettingsToken):
            return super().__eq__(value)
    
    def __hash__(self):
        return super().__hash__()'''

    @property
    def primary_value(self):
        return self.primary_token.raw_value if self.primary_token else self.raw_value
    
    #this method is not called for creation of subclasses if they have overridden
    #don't do anything fancy here
    @classmethod
    def create(cls, value, settings, field, primary_attrib=None):
        if primary_attrib is None:
            primary_attrib = value
        primary_token = cls.objects.filter(
            raw_value=primary_attrib, 
            parent_settings=settings, 
            field_key=field
        ).first()
        print(value, settings, field, primary_attrib)
        obj, _ = cls.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field)
        return obj
    
    class Meta:
        abstract = True
    

    @classmethod    
    def join_input_phrases(cls, input_str, max_len=4):
        #print("TOP: ", input_str)

        input_tokens = re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', input_str.lower())          
        joined_input_tokens = []

        for n in range(max_len, 0, -1):
            for i in range(len(input_tokens) - n + 1):
                phrase = " ".join(input_tokens[i:i+n])
                joined_input_tokens.append(phrase)
        return joined_input_tokens

    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, return_first_match=True, max_len=4):
        #print("me:", input_str)

        #doing this joining repeatedly will cause previously un-adjacent strings to be adjacent after the first match/extract
        #problem?
        joined_input_phrases = cls.join_input_phrases(input_str, max_len)

        #find a(ny) matching settingsToken belonging to the Settings obj
        #matching_tokens = cls.objects.filter(parent_settings=applied_settings, field_key=key, raw_value__in=joined_input_phrases).all()
        query = Q()
        for phrase in joined_input_phrases:
            query |= Q(raw_value__iexact=phrase)

        matching_tokens = cls.objects.filter(
            parent_settings=applied_settings,
            field_key=key,
            disabled_date__isnull=True
        ).filter(query).all()
        #print(joined_input_phrases)
        #print("***", matching_tokens)
        matching_tokens_sorted = sorted(
            matching_tokens,
            key=lambda token: (
                -len(token.raw_value.split()),     # Word count (descending)
                -len(token.raw_value),             # Character count (descending)
                token.raw_value.lower()            # Alphabetical (ascending)
            )
        )
        title, token, new_tokens = cls.process_token_matches(input_str, matching_tokens_sorted, current_tokens, key, return_first_match)
        return title, token, new_tokens

    @classmethod  
    def process_token_matches(cls, input_str, sorted_matches, current_tokens, key, return_first_match=True):
        return_str = input_str
        new_tokens = []
        for token in sorted_matches:

            phrase = token.raw_value
            pattern = rf"\b{re.escape(phrase)}\b"

            if token.match_source_formatting:
                #re-grab from the string itself to guarantee case
                match = re.search(pattern, return_str, flags=re.IGNORECASE)
                phrase = match.group(0) if match else None
        
            # Remove it from the original title (best effort)
            return_str = re.sub(pattern, "", return_str, flags=re.IGNORECASE).strip()            

            #TODO: ultimately let's store these as relations to the matching tokens
            if key in current_tokens:
                current_tokens[key].append(token)
            else:
                current_tokens[key] = [token]
            new_tokens.append(token)

            if return_first_match:
                return return_str, current_tokens, new_tokens
        
        return return_str, current_tokens, new_tokens

class CardNumber(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="cardnr") 
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="cardnr", default=1)

    @classmethod    
    #TODO:ultimately need to remove current_tokens and just return the new tokens
    def match_extract(cls, input_str, current_tokens, key, applied_settings, return_first_match=True, max_len=4):
        #print("me:", input_str)
        #most of the top of this can be abstracted up to SettingToken
        #this method can also probably be shared with serial number
        #print("TOP: ", input_str, key)
        title_clean = input_str.lower()
        new_tokens = []
        # Match formats like "#23", "RC-12", "A7", "23"
        pattern = r'\b#?[a-z0-9]{1,6}(?:-[a-z0-9]{1,6})?\b'
        matches = re.findall(pattern, title_clean)
        reduced = input_str

        # Filter to ensure at least one digit is present
        valid = [m for m in matches if any(c.isdigit() for c in m)]
        reduced = input_str
        if valid:
            card_number = valid[0].lstrip("#")  # Strip leading '#' if present
            reduced = re.sub(rf'\b#?{re.escape(card_number)}\b', "", input_str, flags=re.IGNORECASE).strip()
            current_tokens[key] = [card_number.upper()]
            #TODO:why isn't this value being ccapped properly when displayed?  assuming it has something to do with it not being persisted
            new_tokens = [CardNumber.create(value=card_number.upper(), settings=applied_settings, field=key)]
        return reduced, current_tokens, new_tokens

class SerialNumber(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="serial")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="serialnr", default=1)

    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, return_first_match=True, max_len=4):
        #print("me:", input_str)
        """
        Extracts a serial number like '/250' from a title string.
        Returns (serial_string, reduced_title).
        """
        return_str = input_str
        new_tokens = []
        match = re.search(r"/\d{1,6}\b", input_str)
        if match:
            serial = match.group(0)
            return_str = re.sub(re.escape(serial), "", input_str, flags=re.IGNORECASE).strip()
            current_tokens[key] = [serial]
            #TODO: for now I just never want a serial number
            new_tokens = [SerialNumber.create(value="", settings=applied_settings, field=key)]
            return return_str, current_tokens, new_tokens
        return return_str, current_tokens, new_tokens

class Season(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="season") 
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="year", default=1)

    #this needs cleanup
    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, return_first_match=True, max_len=4):
        #print("me:", input_str)
        title_clean = input_str.lower()
        reduced = input_str
        normalized = None
        new_tokens = []
        # First: match compound years like "1996-97", "1996 97", etc.
        compound_match = re.search(r"\b(19\d{2}|20[0-2]\d)[\s\-–](\d{2})\b", title_clean)
        if compound_match:
            main, tail = int(compound_match.group(1)), int(compound_match.group(2))
            if 1900 <= main <= 2035 and (tail < 10 or tail > 70):
                normalized = normalized = f"{main} {compound_match.group(2)}"
                current_tokens[key] = [normalized]
                reduced = re.sub(re.escape(compound_match.group(0)), "", input_str, flags=re.IGNORECASE).strip()
                new_tokens = [Season.create(value=normalized, settings=applied_settings, field=key)]
                return reduced, current_tokens, new_tokens

        # Second: match standalone 4-digit years
        single_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", title_clean)
        if single_match:
            year = single_match.group(1)
            reduced = re.sub(rf"\b{year}\b", "", input_str, flags=re.IGNORECASE).strip()
            current_tokens[key] = [year]
            new_tokens = [Season.create(value=year, settings=applied_settings, field=key)]
            return reduced, current_tokens, new_tokens

        return reduced, current_tokens, new_tokens

class Brand(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="brands") 
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="brands", default=1)

    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")
    
class Subset(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="subsets")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="subsets", default=1)
    parent_brand = models.ForeignKey(Brand, on_delete=models.CASCADE, default=1, related_name="subsets")

    def __str__(self):
        return f"{self.parent_brand.raw_value} {self.raw_value}"
    
    @classmethod
    def create(cls, value, settings, field, brand):
        subs_obj, _ = Subset.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field, parent_brand=brand)
        return subs_obj
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key", "parent_brand") 
    
class City(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="cities")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="cities", default=1)
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")

class Team(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="teams")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="teams", default=1)
    home_city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="teams", default=1)
    
    def __str__(self):
        return f"{self.home_city.raw_value} {self.raw_value}"
    
    @classmethod
    def create(cls, value, settings, field, city):
        team_obj, _ = Team.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field, home_city=city)
        return team_obj
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key", "home_city") 

class KnownName(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="names") 
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="names", default=1)
    is_full = models.BooleanField(default=False)
    is_first = models.BooleanField(default=False)
    is_last = models.BooleanField(default=False)
    
    @classmethod
    def create(cls, value, settings, field, is_first=False, is_last=False):
        name_obj, _ = KnownName.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field, is_full=(value.index(" ") > -1), is_first=is_first, is_last=is_last)
        return name_obj
    
    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, return_first_match=True, max_len=4):
        #print("me:", input_str)
        joined_input_phrases = SettingsToken.join_input_phrases(input_str, max_len)

        #find a(ny) matching settingsToken belonging to the Settings obj
        full_or_first_filter = (Q(is_first=True) | Q(is_full=True))
        last_name_filter = (Q(is_last=True))

        query = Q()
        for phrase in joined_input_phrases:
            query |= Q(raw_value__iexact=phrase)

        full_or_first_tokens = cls.objects.filter(full_or_first_filter, parent_settings=applied_settings,field_key=key).filter(query).all()

        
        last_name_tokens = cls.objects.filter(last_name_filter, parent_settings=applied_settings, field_key=key, raw_value__in=joined_input_phrases).all()
        sort_key = lambda token: (-token.is_full, -len(token.raw_value), token.raw_value.lower())
        full_or_first_tokens_sorted = sorted(full_or_first_tokens,key=sort_key)
        last_name_tokens_sorted = sorted(last_name_tokens, key=lambda token: (-len(token.raw_value), token.raw_value.lower()))
        #print("me2:", full_or_first_tokens_sorted)
        #print("me2:", last_name_tokens_sorted)
        title, tokens, new_tokens = SettingsToken.process_token_matches(input_str, full_or_first_tokens_sorted, current_tokens, key, True)
        
        if new_tokens and new_tokens[0].is_first:
            title, tokens, new_tokens = SettingsToken.process_token_matches(title, last_name_tokens_sorted, tokens, key, True)
            
            if new_tokens and new_tokens[0]:
                tokens[key] += " "+new_tokens[0]
        return title, tokens, new_tokens

    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")
    
class CardAttribute(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="attribs") 
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="attribs", default=1)

    @classmethod
    def create(cls, value, settings, field, primary_attrib=""):
        name_obj, _ = CardAttribute.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field, primary_attrib=primary_attrib)
        return name_obj
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")

class Condition(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="condition")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="conditions", default=1)
    ebay_id_value = models.CharField(max_length=50, blank=True)
    ebay_string_value = models.CharField(max_length=50, blank=True)
    
    @classmethod
    def create(cls, value, settings, field, primary_attrib="", eid="0", val_string="Unspecified"):
        #print("here")
        condition_obj, _ = Condition.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field, ebay_id_value=eid, ebay_string_value=val_string)
        #print(condition_obj)
        #set this second since it could point to self
        if primary_attrib == value:
            condition_obj.primary_token = condition_obj
        else:
            condition_obj.primary_token= Condition.objects.get(raw_value=primary_attrib)
        
        condition_obj.save()
        return condition_obj
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")

class Parallel(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="parallel")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="parallel", default=1)
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")

class CardName(SettingsToken):
    field_key = models.CharField(max_length=100, blank=False, default="card_name")
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="card_name", default=1)
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")
