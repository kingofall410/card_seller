from django.contrib import admin
from core.models.Card import Card, CardSearchResult, Collection
from core.models.ListingGroup import ListingGroup
from core.models.ProductListing import ProductListing, ListingTitle
from core.models.ProductGroup import ProductGroup
from core.models.ListedInfo import ListedInfo
from core.models.ListingStatus import ListingStatus
from core.models.Cropping import CropParams, CroppedImage
from core.models.TagGroup import TagGroup
from core.models.Archive import CardArchive, CSRArchive, CroppedImageArchive, ListedInfoArchive

@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ['id', 'modification_date']


@admin.register(CardSearchResult)
class CardSearchResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'title_to_be', 'ebay_product_group', 'overall_status', 'ebay_msrp', 'ebay_listing_id', 'sku', 'list_price']
    def get_form(self, request, obj=None, **kwargs):
        model_fields = [f.name for f in self.model._meta.many_to_many]
        print("Model fields:", model_fields)
        exclude_fields = [name for name in model_fields if not 'available' in name]
        kwargs['exclude'] = exclude_fields
        print("Excluding fields:", exclude_fields)

        return super().get_form(request, obj, **kwargs)


@admin.register(ListingGroup)
class CardAdmin(admin.ModelAdmin):
    list_display = ['id']

admin.site.register(ProductListing)
admin.site.register(ListingTitle)
admin.site.register(CropParams)
admin.site.register(CroppedImage) 
admin.site.register(Collection)
admin.site.register(ListingStatus)
admin.site.register(ListedInfoArchive)
admin.site.register(CardArchive)
admin.site.register(CSRArchive)
admin.site.register(CroppedImageArchive)

@admin.register(ProductGroup)
class ProductGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'group_key', 'group_title', 'size']

@admin.register(TagGroup)
class TagGroupAdmin(admin.ModelAdmin):
    list_display = ['id', 'group_key', 'group_title', 'size']

@admin.register(ListedInfo)
class ListedInfoAdmin(admin.ModelAdmin):
    readonly_fields = ('modification_date',)
    list_display = ('__str__', 'modification_date')
#-gold -chrome -yellow -green -red -blue -refractor -psa -sgc -cgc -purple -rainbow -foil -aqua -wave -raywave -logofractor -x-fractor