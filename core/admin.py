from django.contrib import admin
from .models.Card import Card, CardSearchResult, Collection
from core.models.CardSearchResult import ProductListing, ListingTitle
from core.models.Cropping import CropParams, CroppedImage

admin.site.register(Card)
admin.site.register(CardSearchResult)
admin.site.register(ProductListing)
admin.site.register(ListingTitle)
admin.site.register(CropParams)
admin.site.register(CroppedImage)
admin.site.register(Collection)


