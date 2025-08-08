from django.db import models
from django.contrib.auth.models import User
from dataclasses import dataclass
import re

class Settings(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, default=1, related_name="active_settings")    
    nr_returned_listings = models.IntegerField(default=10)
    nr_collection_page_items = models.IntegerField(default=10)

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
 
    def __str__(self):
        return f"{self.raw_value}"
    
    #this method is not called for creation of subclasses if they have overridden
    #don't do anything fancy here
    @classmethod
    def create(cls, value, settings, field):
        obj, _ = cls.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field)
        return obj
    
    class Meta:
        abstract = True
    
    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, max_len=4, return_first_match=True):
            print("TOP: ", input_str, key)
            input_tokens = re.findall(r'[a-z0-9]+', input_str.lower())          
            joined_input_tokens = []
            return_str = input_str

            for n in range(max_len, 0, -1):
                for i in range(len(input_tokens) - n + 1):
                    phrase = " ".join(input_tokens[i:i+n])
                    joined_input_tokens.append(phrase)

            #find a(ny) matching settingsToken belonging to the Settings obj
            matched_settings_tokens = cls.objects.filter(parent_settings=applied_settings, field_key=key, raw_value__in=joined_input_tokens).all()
            matched_settings_tokens_sorted = sorted(
                matched_settings_tokens,
                key=lambda token: len(token.raw_value.split()),
                reverse=True
            )

            for token in matched_settings_tokens_sorted:
                
                phrase = token.raw_value

                if key in current_tokens:
                    current_tokens[key].append(phrase)
                else:
                    current_tokens[key] = [phrase]

                # Remove it from the original title (best effort)
                pattern = rf"\b{re.escape(phrase)}\b"
                return_str = re.sub(pattern, "", return_str, flags=re.IGNORECASE).strip()

                if return_first_match:
                    return return_str, current_tokens
            
            return return_str, current_tokens

class CardNumber(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="cardnr", default=1)

    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, max_len=4, return_first_match=True):
        
        #most of the top of this can be abstracted up to SettingToken
        #this method can also probably be shared with serial number
        print("TOP: ", input_str, key)
        title_clean = input_str.lower()

        # Match formats like "#23", "RC-12", "A7", "23"
        pattern = r'\b#?[a-z0-9]{1,4}(?:-[a-z0-9]{1,4})?\b'
        matches = re.findall(pattern, title_clean)
        reduced = input_str

        # Filter to ensure at least one digit is present
        valid = [m for m in matches if any(c.isdigit() for c in m)]
        reduced = input_str
        if valid:
            card_number = valid[0].lstrip("#")  # Strip leading '#' if present
            reduced = re.sub(rf'\b#?{re.escape(card_number)}\b', "", input_str, flags=re.IGNORECASE).strip()
            current_tokens[key] = [card_number]

        return reduced, current_tokens

class SerialNumber(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="serialnr", default=1)

    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, max_len=4, return_first_match=True):
        """
        Extracts a serial number like '/250' from a title string.
        Returns (serial_string, reduced_title).
        """
        return_str = input_str
        match = re.search(r"/\d{1,6}\b", input_str)
        if match:
            serial = match.group(0)
            return_str = re.sub(re.escape(serial), "", input_str, flags=re.IGNORECASE).strip()
            current_tokens[key] = [serial]
            return return_str, current_tokens
        return return_str, current_tokens

class Season(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="season", default=1)

    #this needs cleanup
    @classmethod    
    def match_extract(cls, input_str, current_tokens, key, applied_settings, max_len=4, return_first_match=True):
        title_clean = input_str.lower()
        reduced = input_str
        normalized = None
        # First: match compound years like "1996-97", "1996 97", etc.
        compound_match = re.search(r"\b(19\d{2}|20[0-2]\d)[\s\-–](\d{2})\b", title_clean)
        if compound_match:
            main, tail = int(compound_match.group(1)), int(compound_match.group(2))
            if 1900 <= main <= 2035 and (tail < 10 or tail > 70):
                normalized = normalized = f"{main} {compound_match.group(2)}"
                current_tokens[key] = [normalized]
                reduced = re.sub(re.escape(compound_match.group(0)), "", input_str, flags=re.IGNORECASE).strip()
                return reduced, current_tokens
            
        # Second: match standalone 4-digit years
        single_match = re.search(r"\b(19\d{2}|20[0-2]\d)\b", title_clean)
        if single_match:
            year = single_match.group(1)
            reduced = re.sub(rf"\b{year}\b", "", input_str, flags=re.IGNORECASE).strip()
            current_tokens[key] = [year]
            return reduced, current_tokens

        return reduced, current_tokens

class Brand(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="brands", default=1)

    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")
    
class Subset(SettingsToken):
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
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="cities", default=1)
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")

class Team(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="teams", default=1)
    home_city = models.ForeignKey(City, on_delete=models.CASCADE, related_name="teams", default=1)
    
    def __str__(self):
        return f"{self.home_city.raw_value} {self.raw_value}"
    
    @classmethod
    def create(cls, value, settings, field, city):
        team_obj, _ = Team.objects.get_or_create(raw_value=value, parent_settings=settings, field_key=field, home_city=city)
        return team_obj
    
    class Meta:
        pass
        unique_together = ("raw_value", "parent_settings", "field_key", "home_city") 

class KnownName(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="names", default=1)
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")
    
class CardAttribute(SettingsToken):
    parent_settings = models.ForeignKey(Settings, on_delete=models.CASCADE, related_name="attribs", default=1)
    
    class Meta:
        unique_together = ("raw_value", "parent_settings", "field_key")
