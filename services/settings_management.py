import io, csv
from services.models import Brand, Subset, Team, City, KnownName, CardAttribute, User, Condition, Parallel, Settings
from django.shortcuts import render, redirect
    
def load_settings_file(dj_file, file_type, user_settings=None):
    
    dj_file.seek(0)
    text_stream = io.TextIOWrapper(dj_file, encoding="utf-8")
    reader = csv.reader(text_stream)

    if not user_settings:
        user_settings = User.objects.first().active_settings.first()

    if file_type == "brands":     
        
        subset_set = set(((row[0]).strip(), (row[1]).strip()) for row in reader if row and len(row) > 1)
        print(subset_set)
        for subset_str, brand_str in subset_set:
            #print(subset_str, brand_str)
            try:
                brand_obj = Brand.create(value=brand_str, settings=user_settings, field=file_type)
            except Exception as e:
                print(f"Error creating brand '{brand_str}':", e)
            try:
                Subset.create(value=subset_str, settings=user_settings, field="subsets", brand=brand_obj )
            except Exception as e:
                print(f"Error creating subset '{subset_str}':", e)

    elif file_type == "teams":
        
        name_city_set = set(((row[0]).strip(), (row[1]).strip()) for row in reader if row and len(row) > 1)
        
        for team_name, city_name in name_city_set:
            
            try:            
                city_obj, _ = City.objects.get_or_create(raw_value=city_name, parent_settings=user_settings, field_key="cities")
            except Exception as e:
                print(f"Error creating city '{city_name}':", e)
            try:
                
                Team.objects.get_or_create(raw_value=team_name, home_city=city_obj, parent_settings=user_settings, field_key=file_type)
            except Exception as e:
                print(f"Error creating team '{team_name}':", e)
    elif file_type == "condition":
        
        condition_primary_set = set(((row[0]).strip(), (row[1]).strip(), (row[2]).strip(), (row[3]).strip()) for row in reader if row and len(row) > 1)
        print(condition_primary_set)
        for condition,primary, id, val_string in condition_primary_set:
            print(condition)
            print(primary)
            print(id, val_string)
            Condition.create(condition, user_settings, file_type, primary_attrib=primary, eid=id, val_string=val_string)
    else:
        
        keyword_set = set((row[0]).strip() for row in reader if row and len(row) > 0)
        #print(keyword_set)
        for keyword in keyword_set:
            #print(keyword)
            try:
                if file_type == "names":
                    KnownName.objects.get_or_create(raw_value=keyword, parent_settings=user_settings, field_key=file_type)
                elif file_type == "attribs":
                    CardAttribute.objects.get_or_create(raw_value=keyword, parent_settings=user_settings, field_key=file_type)
                
                elif file_type == "parallel":
                    Parallel.objects.get_or_create(raw_value=keyword, parent_settings=user_settings, field_key=file_type)
                else:#random filenames get read in as names
                    KnownName.objects.get_or_create(raw_value=keyword, parent_settings=user_settings, field_key="names")

            except Exception as e:
                print(f"Error creating keyword '{keyword}':", e)

def add_token(field_key, value, all_field_data, user_settings=None):
    new_obj = None
    if not user_settings:
        user_settings = User.objects.first().active_settings.first()
    
    if field_key == "brands" or field_key == "brand": 
        new_obj = Brand.create(value=value, settings=user_settings, field=field_key)

    elif field_key == "subsets" or field_key == "subset":
        brand_obj = None
        if all_field_data:
            brand_obj = Brand.objects.get(raw_value=all_field_data["brand"], disabled_date=None)
        
        if brand_obj:
            new_obj = Subset.create(value=value, settings=user_settings, field=field_key, brand=brand_obj)
        else:
            #TODO: this should actually probably throw an error, but it needs to be allowed for collapse
            new_obj = Subset.objects.filter(raw_value=value).first()

    elif field_key == "cities" or field_key == "city":   
        new_obj = City.create(value=value, settings=user_settings, field=field_key)

    elif field_key == "teams" or field_key == "team":

        city_obj = None
        if all_field_data:
            city_obj = City.objects.get(raw_value=all_field_data["city"], disabled_date=None)
            #print(city_obj)
        
        if city_obj:
            new_obj = Team.create(value=value, settings=user_settings, field=field_key, city=city_obj)
        else:
            #TODO: this should actually probably throw an error, but it needs to be allowed for collapse
            new_obj = Team.objects.filter(raw_value=value).first()

    elif field_key == "names" or field_key == "full_name":
        new_obj = KnownName.create(value=value, settings=user_settings, field="names")
    elif field_key == "attribs" or field_key == "attributes": 
        new_obj = CardAttribute.create(value=value, settings=user_settings, field=field_key)
    elif field_key == "condition":
        new_obj = Condition.create(value=value, settings=user_settings, field=field_key)
    elif field_key == "parallel":
        new_obj = Parallel.create(value=value, settings=user_settings, field=field_key)
    
    return new_obj
