from django.contrib import admin
from .models.Card import Card, CardSearchResult, Collection
from core.models.CardSearchResult import ProductListing, ListingTitle
from core.models.Cropping import CropParams, CroppedImage

admin.site.register(Card)
@admin.register(CardSearchResult)
class CardSearchResultAdmin(admin.ModelAdmin):
    def get_form(self, request, obj=None, **kwargs):
        model_fields = [f.name for f in self.model._meta.fields]
        exclude_fields = [f for f in model_fields if f.startswith('available')]
        kwargs['exclude'] = exclude_fields
        return super().get_form(request, obj, **kwargs)

admin.site.register(ProductListing)
admin.site.register(ListingTitle)
admin.site.register(CropParams)
admin.site.register(CroppedImage)
admin.site.register(Collection)


