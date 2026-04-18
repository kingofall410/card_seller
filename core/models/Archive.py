from django.db import models
from django.db import transaction
from django.forms.models import model_to_dict
from django.core.files.storage import default_storage
from django.core.serializers.json import DjangoJSONEncoder

class CroppedImageArchive(models.Model):

    original_id = models.IntegerField() # Keep reference to the old PK
    path = models.CharField(max_length=500, default="")
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['original_id'])]

    @classmethod
    def rehydrate(cls, archive_id):
        from core.models.Cropping import CroppedImage
        if not archive_id: return None
        
        arc = cls.objects.get(id=archive_id)
        print("arc", arc.id)
        # Move file back
        original_path = arc.path.replace("archive/", "")
        with default_storage.open(arc.path) as source:
            default_storage.save(original_path, source)
        
        # Create production model
        return CroppedImage.objects.create(
            id=arc.original_id,
            img=original_path
        )


    @classmethod
    def archive(cls, card_id, id):
        from core.models.Cropping import CroppedImage
        try:
            # 1. Fetch
            im = CroppedImage.objects.get(id=id)
            
            new_path = f"archive/{im.img.name}"
            default_storage.save(new_path, im.img.open())

            # 3. Save to Archive
            cia = CroppedImageArchive.objects.create(
                original_id=id,
                path=new_path
            )
            
            # 4. Delete Original
            im.delete()
            return cia
        except CroppedImage.DoesNotExist:
            return False

class CSRArchive(models.Model):
    
    original_id = models.IntegerField() # Keep reference to the old PK
    data = models.JSONField()           # The dump of the task object

    @classmethod
    def rehydrate(cls, card, archive_id):
        from core.models.CardSearchResult import CardSearchResult
        from core.models.Status import StatusBase
        if not archive_id: return None
        
        arc = cls.objects.get(id=archive_id)
        print("arc", arc.id)
                
        # Create production model
        csr = CardSearchResult.objects.create(parent_card=card, **arc.data)
        csr.overall_status = StatusBase.REHYDRATED
        csr.save()

    @classmethod
    def archive(cls, card_id, csr):
        from core.models.CardSearchResult import CardSearchResult
        try:
            exclusions = [f.name for f in csr._meta.many_to_many]

            # 2. Add all Foreign Keys and OneToOneFields dynamically
            # We check if the field is a relation (Foreign Key or OneToOne)
            for field in csr._meta.fields:
                if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    exclusions.append(field.name)

            # 3. Add your manual hardcoded exclusions
            exclusions += [
                'parent_card_id', 'text_search_string', 'text_search_string_m', 
                'text_search_string_is_manual', 'sold_search_string', 
                'sold_search_string_m', 'sold_search_string_is_manual', 
                'front_crop_params', 'reverse_crop_params', 'ebay_listed_under_sku'
            ]
            
            csr_data = model_to_dict(csr, exclude=exclusions) 

            # 3. Save to Archive
            csra = CSRArchive.objects.create(
                original_id=csr.id,
                data=csr_data
            )

            # 4. Delete Original
            csr.delete()
            return csra
        except CSRArchive.DoesNotExist:
            return False

class ListedInfoArchive(models.Model):

    original_id = models.IntegerField() # Keep reference to the old PK
    original_pg = models.IntegerField() # Keep reference to the old PK
    data = models.JSONField()           # The dump of the task object
    original_dt = models.DateTimeField(null=True)

    @classmethod
    def rehydrate(cls, card, archive_id):
        from core.models.ListedInfo import ListedInfo
        if not archive_id: return None
        
        arc = cls.objects.get(id=archive_id)
        print("arc", arc.id)
                
        # Create production model
        li = ListedInfo.objects.create(card_id=card.id, listing_datetime=arc.original_dt, **arc.data)
        if arc.original_pg >= 0:
            li.product_group_id = arc.original_pg 
        li.save()
        return li

    @classmethod
    def archive(cls, card_id, li):
        from core.models.ListedInfo import ListedInfo
        try:
            exclusions = ['card', 'sub_cards', 'product_group', 'listing_datetime']            
            li_data = model_to_dict(li, exclude=exclusions)

            # 3. Save to Archive
            lia = ListedInfoArchive.objects.create(
                original_id=li.id,
                data=li_data,
                original_pg=li.product_group_id or -1,
                original_dt = li.listing_datetime
            )

            # 4. Delete Original
            li.delete()
            return lia
        except ListedInfoArchive.DoesNotExist:
            return False

class CardArchive(models.Model):

    original_id = models.IntegerField() # Keep reference to the old PK
    data = models.JSONField()           # The dump of the task object
    cropped_img_archive = models.OneToOneField(CroppedImageArchive, on_delete=models.CASCADE, related_name="card_as_primary")
    cropped_rev_archive = models.OneToOneField(CroppedImageArchive, on_delete=models.CASCADE, related_name="card_as_reverse")
    asr = models.ForeignKey(CSRArchive, on_delete=models.CASCADE, null=True, related_name='parent_card')
    li = models.ForeignKey(ListedInfoArchive, on_delete=models.CASCADE, null=True, related_name='parent_card')
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['original_id'])]

    @classmethod
    def rehydrate(cls, archive_match_kv, collection_id):
        from core.models.Card import Card, Collection
        from django.db import transaction, connection

        with transaction.atomic():
            arc = cls.objects.get(**archive_match_kv)
            collection = Collection.objects.get(id=collection_id)
            
            print("\n" + "="*50)
            print(f"STEP 1: Archiving original_id: {arc.original_id}")

            # 1. Image Rehydration
            print("STEP 2: Rehydrating Images...")
            cropped_image = CroppedImageArchive.rehydrate(arc.cropped_img_archive_id)
            cropped_reverse = CroppedImageArchive.rehydrate(arc.cropped_rev_archive_id)

            # 2. Card Creation
            # MONITOR: Does your Card.create() method trigger a signal?
            print("STEP 3: Calling Card.create(collection)...")
            card = Card.create(collection, create_li=False)
            print(f"   -> Card created! New DB ID: {card.id}")

            # 3. Data Application
            print("STEP 4: Applying archived data to Card instance...")
            data = arc.data.copy()
            if 'id' in data:
                print(f"   -> Found 'id' {data['id']} in arc.data. REMOVING to prevent collision.")
                data.pop('id', None)
            
            for key, value in data.items():
                if hasattr(card, key):
                    setattr(card, key, value)
            
            card.cropped_image = cropped_image
            card.cropped_reverse = cropped_reverse
            
            print("STEP 5: Executing card.save()...")
            card.save()
            print(f"   -> card.save() successful. Current ID is {card.id}")

            # 4. The Children (The most likely spot for 'Creating Twice')
            print(f"STEP 6: Rehydrating CSR for Card {card.id}...")
            # CHECK: If a signal already created a CSR when Card.create() ran, this will FAIL.
            CSRArchive.rehydrate(card, arc.asr_id)
            
            print(f"STEP 7: Rehydrating ListedInfo for Card {card.id}...")
            # CHECK: If a signal already created ListedInfo, this will FAIL.
            ListedInfoArchive.rehydrate(card, arc.li_id)
            
            print("SUCCESS: Rehydration complete.")
            print("="*50 + "\n")

        return card

    @classmethod
    def archive(cls, card_id):
        from core.models.Card import Card
        with transaction.atomic():
            try:
                # 1. Fetch
                card = Card.objects.get(id=card_id)
                csr = card.search_results.last()
                li = card.listed_card_info
                # 2. Dump to JSON (using model_to_dict)
                # Exclude fields that don't serialize well (like FileFields)
                card_data = model_to_dict(card, fields=['upload_date', 'reverse_id', 'notes', 'value', 'modification_date']) 
                img_arc = CroppedImageArchive.archive(card_id, card.cropped_image_id)
                rev_arc = CroppedImageArchive.archive(card_id, card.cropped_reverse_id)
                csr_arc = CSRArchive.archive(card_id, csr)
                li_arc = ListedInfoArchive.archive(card_id, li)
                
                # 3. Save to Archive
                ca = CardArchive.objects.create(
                    original_id=card_id,
                    data=card_data,
                    cropped_img_archive=img_arc,
                    cropped_rev_archive=rev_arc,
                    asr=csr_arc,
                    li=li_arc
                )
                
                # 4. Delete Original
                card.delete()
                return True
            except CardArchive.DoesNotExist:
                return False