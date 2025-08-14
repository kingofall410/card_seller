import csv, io
from core.models.CardSearchResult import CardSearchResult
from django.http import HttpResponse
import zipfile
from services import ebay
from services.google import GoogleDriveUploader

def export_csrs_to_csv(csrs):
    """Exports Card objects to CSV and returns a downloadable response."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="card_collection.csv"'

    writer = csv.writer(response)
    writer.writerow(CardSearchResult.listing_fields + CardSearchResult.dynamic_listing_fields)
    
    for csr in csrs:
        writer.writerow(csr.export_to_csv())

    return response


def export_zip(csrs):
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="card_collection.csv"'
    writer = csv.writer(response)
    
    writer.writerow(ebay.singles_excel_fields.keys())
            
    uploader = GoogleDriveUploader()
   
    for csr in csrs:
        shareable_link_front = uploader.upload_and_share(csr.get_latest_front(), csr.title_to_be)
        shareable_link_reverse = uploader.upload_and_share(csr.get_latest_reverse(), csr.title_to_be)
        #print("🔗 Public link:", shareable_link_front)
        #print("🔗 Public link:", shareable_link_reverse)
        writer.writerow(csr.export_to_csv(ebay.singles_excel_fields) + [shareable_link_front, shareable_link_reverse])

    return response