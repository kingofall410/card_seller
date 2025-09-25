from django.urls import path
from .views import (
    misc_views,
    ajax_views,
    card_views,
    collection_views,
    export_views,
    image_views,
    search_views,
    settings_views,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('hello/', misc_views.hello_world),
    path('get_dynamic_options/', search_views.get_dynamic_options, name='get_dynamic_options'),
    path('test/', misc_views.test_view, name="test_view"),
    path('delete/', card_views.delete, name="delete"),
    path('crop_review/<int:collection_id>/', card_views.crop_review, name="crop_review"),
    path('full_crop/<int:card_id>', card_views.full_crop, name="full_crop"),
    path('save_and_next/<int:card_id>', card_views.save_and_next, name="save_and_next"),
    path('next/<int:card_id>', card_views.next_card, name="next_card"),    
    path("upload_image/", image_views.upload_image, name="upload_image"),
    path("upload_image/<int:collection_id>", image_views.upload_image, name="upload_image"),    
    path('image_search/<int:card_id>/', search_views.image_search, name='image_search'),
    path('retokenize/<int:csr_id>/', card_views.retokenize, name='retokenize'),
    path('image_search_collection/<int:collection_id>/', search_views.image_search_collection, name='image_search_collection'),
    path('text_search/<int:card_id>/', search_views.text_search, name='text_search'),
    path('text_search_collection/<int:collection_id>/', search_views.text_search_collection, name='text_search_collection'),
    path("upload_crop/", image_views.upload_crop, name="upload_crop"),
    path("update_tokens/", ajax_views.add_token, name="add_token"),
    path("add_token/", ajax_views.add_token, name="add_token"),
    #path("load-file/", upload_views.load_file, name="load_file"),
    path("settings/", settings_views.view_settings, name="settings"),
    path("update_settings/", settings_views.update_settings, name="update_settings"),
    path("collection/<int:collection_id>", collection_views.view_collection, name="collection"),
    path("card/<int:card_id>/", card_views.view_card, name="view_card"),
    path("settings/upload/<str:file_type>/", settings_views.settings_file_upload, name="settings_file_upload"),
    path("update_csr_fields/", card_views.update_csr_fields, name="update_csr_fields"),
    path("update_collection/", collection_views.update_collection, name="update_collection"),
    #path('register-field/', ajax_views.register_field, name='register_field'),
    #path('save_overrides/<int:card_id>/', card_views.save_overrides, name='save_overrides'),
    path('export/<int:csr_id>/', export_views.export, name='export'),
    path('hold_card/<int:csr_id>/', card_views.hold_card, name='hold_card'),
    path('list_card/<int:csr_id>/', export_views.list_card, name='list_card'),
    path('export_collection/<int:collection_id>/', collection_views.export_collection, name='export_collection'),
    path('manage/', collection_views.manage_collection, name='manage_collection'),
    path('move_to_collection/<int:card_id>/<int:collection_id>', collection_views.move_to_collection, name="move_to_collection"),
    path('move_to_collection/', collection_views.move_to_collection2, name="move_to_collection2")

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
