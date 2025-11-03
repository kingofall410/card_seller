from django.contrib import admin
from .models.Card import Card, CardSearchResult, Collection
from core.models.CardSearchResult import ProductListing, ListingTitle, ListingGroup, ProductGroup
from core.models.Cropping import CropParams, CroppedImage

admin.site.register(Card)
@admin.register(CardSearchResult)
class CardSearchResultAdmin(admin.ModelAdmin):
    list_display = ['id', 'title_to_be', 'filter_terms', 'ebay_product_group']
    def get_form(self, request, obj=None, **kwargs):
        model_fields = [f.name for f in self.model._meta.many_to_many]
        print("Model fields:", model_fields)
        exclude_fields = [name for name in model_fields if 'available' in name]
        kwargs['exclude'] = exclude_fields
        print("Excluding fields:", exclude_fields)

        return super().get_form(request, obj, **kwargs)


admin.site.register(ProductListing)
admin.site.register(ListingTitle)
admin.site.register(CropParams)
admin.site.register(CroppedImage)
admin.site.register(Collection)
admin.site.register(ListingGroup)
admin.site.register(ProductGroup)


#-gold -chrome -yellow -green -red -blue -refractor -psa -sgc -cgc -purple -rainbow -foil -aqua -wave -raywave -logofractor -x-fractor