from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('hello/', views.hello_world),
    path('get_dynamic_options/', views.get_dynamic_options, name='get_dynamic_options'),
    path('test/', views.test_view, name="test_view"),
    path('delete/', views.delete, name="delete"),
    path('crop_review/<int:card_id>', views.crop_review, name="crop_review"),
    path('save_and_next/<int:card_id>', views.save_and_next, name="save_and_next"),
    path('next/<int:card_id>', views.next, name="next"),    
    path("select-directory/", views.upload_folder_and_redirect, name="select_directory"),
    path("upload_image/", views.upload_image, name="upload_image"),
    path("upload_image/<int:collection_id>", views.upload_image, name="upload_image"),    
    path('image_search/<int:card_id>/', views.image_search, name='image_search'),
    path('retokenize/<int:csr_id>/', views.retokenize, name='retokenize'),
    path('image_search_collection/<int:collection_id>/', views.image_search_collection, name='image_search_collection'),
    path('text_search/<int:card_id>/', views.text_search, name='text_search'),
    path('text_search_collection/<int:collection_id>/', views.text_search_collection, name='text_search_collection'),
    path("upload_crop/", views.upload_crop, name="upload_crop"),
    path("update_tokens/", views.add_token, name="add_token"),
    path("add_token/", views.add_token, name="add_token"),
    path("load-file/", views.load_file, name="load_file"),
    path("settings/", views.view_settings, name="settings"),
    path("update_settings/", views.update_settings, name="update_settings"),
    path("collection/", views.view_collection, name="collection_no_id"),
    path("collection/<int:collection_id>", views.view_collection, name="collection"),
    path("collection_create/", views.collection_create, name="collection_create"),
    path("card/<int:card_id>/", views.view_card, name="view_card"),
    path("settings/upload/<str:file_type>/", views.settings_file_upload, name="settings_file_upload"),
    path("update_csr_fields/", views.update_csr_fields, name="update_csr_fields"),
    path("update_collection/", views.update_collection, name="update_collection"),
    path('register-field/', views.register_field, name='register_field'),
    path('save_overrides/<int:card_id>/', views.save_overrides, name='save_overrides'),
    path('export/<int:csr_id>/', views.export, name='export'),
    path('export_collection/<int:collection_id>/', views.export_collection, name='export_collection'),
    path('manage/', views.manage_collection, name='manage_collection'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
