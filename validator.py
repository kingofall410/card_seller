import json
from django.apps import apps
import os
from collections import defaultdict
from django.db import models
from django.core.management import call_command
from django.db import connection
# Set your settings module if not already set
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "card_seller.settings_pg")
import django
django.setup()
def fix_services_specifically(input_path, output_path):
    with open(input_path, 'r') as f:
        data = json.load(f)

    fixed_count = 0
    total_entries = len(data)
    print(f"Scanning {total_entries} entries...")

    for entry in data:
        model_name = entry['model']
        # We only care about services for this run
        if not model_name.startswith('services.'):
            continue
            
        fields = entry['fields']
        pk = entry['pk']
        
        try:
            Model = apps.get_model(model_name)
        except LookupError:
            print(f"Could not find model {model_name}")
            continue

        for field_name, value in fields.items():
            try:
                field = Model._meta.get_field(field_name)
                
                # --- LOGIC FOR NULL VALUES ---
                if value is None and not field.null:
                    print(f"Found NULL violation: {model_name} (PK: {pk}) Field type: {type(field)}")
                    
                    if isinstance(field, (models.CharField, models.TextField)):
                        fields[field_name] = ""
                    elif isinstance(field, models.BooleanField):
                        fields[field_name] = False
                    elif isinstance(field, (models.IntegerField, models.FloatField)):
                        fields[field_name] = 0
                    else:
                        return
                    fixed_count += 1
                    print("fixed count: ", fixed_count)
                
                # --- LOGIC FOR MAX LENGTH ---
                if isinstance(value, str):
                    max_length = getattr(field, 'max_length', None)
                    if max_length and len(value) > max_length:
                        print(f"Found LENGTH violation: {model_name} (PK: {pk}) Field: {field_name}")
                        fields[field_name] = value[:max_length]
                        fixed_count += 1

            except Exception as e:
                print(e)
                continue

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Total issues repaired: {fixed_count}")

def remove_duplicate_pk(input_path, output_path, pk_to_remove):
    with open(input_path, 'r') as f:
        data = json.load(f)
    print(len(data))
    # Filter out the offending PK
    new_data = [entry for entry in data if not ((entry['model'] == 'services.parallel' or entry['model'] == 'services.Parallel') and entry['pk'] == pk_to_remove)]
    
    with open(output_path, 'w') as f:
        json.dump(new_data, f, indent=2)
    
    print(f"✅ Removed services.subset PK {pk_to_remove}. Total entries remaining: {len(new_data)}")

def validate_fixture(fixture_path):
    with open(fixture_path, 'r') as f:
        data = json.load(f)

    errors = 0
    for entry in data:
        model_name = entry['model']
        pk = entry['pk']
        fields = entry['fields']
        
        # Get the model class
        Model = apps.get_model(model_name)
        
        for field_name, value in fields.items():
            if value is None:
                continue
                
            # Get the field object from the model
            try:
                field = Model._meta.get_field(field_name)
                max_length = getattr(field, 'max_length', None)
                
                if max_length and isinstance(value, str) and len(value) > max_length:
                    print(f"❌ ERROR: {model_name} (PK: {pk})")
                    print(f"   Field '{field_name}' is {len(value)} chars, but max_length is {max_length}.")
                    print(f"   Value: {value[:50]}...")
                    errors += 1
            except Exception:
                continue

    if errors == 0:
        print("✅ No length violations found!")
    else:
        print(f"\nFound {errors} total violations.")


def fix_fixture(input_path, output_path):
    with open(input_path, 'r') as f:
        data = json.load(f)

    fixed_count = 0
    for entry in data:
        model_name = entry['model']
        fields = entry['fields']
        Model = apps.get_model(model_name)
        
        for field_name, value in fields.items():
            try:
                field = Model._meta.get_field(field_name)
                
                # --- FIX 1: Handle NOT NULL violations ---
                if value is None and not field.null:
                    if isinstance(field, (models.CharField, models.TextField)):
                        fields[field_name] = ""
                    elif isinstance(field, models.BooleanField):
                        fields[field_name] = False
                    elif isinstance(field, (models.IntegerField, models.FloatField, models.DecimalField)):
                        fields[field_name] = 0
                    fixed_count += 1
                    print(f"Fixed {model_name} PK {entry['pk']}: Set {field_name} to non-null default")
                    # Update 'value' for the next check
                    value = fields[field_name]

                # --- FIX 2: Handle MAX_LENGTH violations ---
                if isinstance(value, str):
                    max_length = getattr(field, 'max_length', None)
                    if max_length and len(value) > max_length:
                        fields[field_name] = value[:max_length]
                        fixed_count += 1
                        print(f"Fixed {model_name} PK {entry['pk']}: Truncated {field_name}")

            except Exception as e:
                # This catches fields that might be defined in the JSON but not in the model
                continue

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\n✅ Success! Repaired {fixed_count} issues. Saved to {output_path}")

def split_fixture(input_file):
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Group data by the app name (the part before the first dot)
    apps = defaultdict(list)
    for entry in data:
        app_name = entry['model'].split('.')[0]
        apps[app_name].append(entry)

    # Save each app's data to a separate file
    for app_name, entries in apps.items():
        output_filename = f"fixed_{app_name}.json"
        with open(output_filename, 'w') as f:
            json.dump(entries, f, indent=2)
        print(f"Created {output_filename} with {len(entries)} entries.")

def load_without_constraints(fixture_file):
    with connection.cursor() as cursor:
        print("Disabling all table triggers (constraints)...")
        # This is a PostgreSQL-specific command that stops FK checks
        cursor.execute("SET session_replication_role = 'replica';")
        
        try:
            print(f"Loading {fixture_file}...")
            call_command('loaddata', fixture_file, verbosity=1)
            print("Successfully loaded data.")
        except Exception as e:
            print(f"Error loading data: {e}")
        finally:
            print("Re-enabling constraints...")
            cursor.execute("SET session_replication_role = 'origin';")

def split_core_into_chunks(input_file, chunk_size=5000):
    print(f"Reading {input_file}... this might take a minute.")
    with open(input_file, 'r') as f:
        data = json.load(f)

    total_records = len(data)
    print(f"Total records found: {total_records}")

    for i in range(0, total_records, chunk_size):
        chunk = data[i:i + chunk_size]
        chunk_num = (i // chunk_size) + 1
        output_filename = f"core_chunk_{chunk_num}.json"
        
        with open(output_filename, 'w') as f:
            json.dump(chunk, f, indent=2)
        print(f"Created {output_filename} ({len(chunk)} records)")

if __name__ == "__main__":
    #validate_fixture('data.json')
    #fix_services_specifically('fixed_services.json', )
    #split_fixture('data_fixed.json')
    #remove_duplicate_pk('fixed_fixed_services4.json', 'fixed_fixed_services5.json', 26)
    #remove_duplicate_pk('fixed_fixed_services2.json', 'fixed_fixed_services3.json')
    #load_without_constraints('fixed_fixed_services4.json')
    split_core_into_chunks('fixed_core.json', chunk_size=5000)