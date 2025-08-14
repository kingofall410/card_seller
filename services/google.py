import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_PATH = 'token.json'  # Stores user's access/refresh token
CREDENTIALS_PATH = 'credentials/credentials.json'  # OAuth client credentials

class GoogleDriveUploader:
    def __init__(self):
        self.creds = None
        self.authenticate()
        self.service = build('drive', 'v3', credentials=self.creds)

    def authenticate(self):
        # Load saved credentials if available
        if os.path.exists(TOKEN_PATH):
            self.creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        # If no valid credentials, start OAuth flow
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                self.creds = flow.run_local_server(port=58695)

            # Save credentials for future use
            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(self.creds.to_json())

    def get_or_create_folder(self, folder_name):
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])

        if folders:
            print(f"🔁 Reusing folder: {folder_name}")
            return folders[0]['id']

        print(f"🆕 Creating folder: {folder_name}")
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = self.service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

    def upload_file(self, file_path, name, folder_id="1DrUwBBNYvKIR6H6p0mOzRJwjzeB8jIpO"):
        
        file_metadata = {'name': name}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        print(f"📤 Uploaded as: {name}")
        
        return file.get('id')

    def make_file_public(self, file_id):
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        self.service.permissions().create(fileId=file_id, body=permission).execute()
        file = self.service.files().get(fileId=file_id, fields='webViewLink').execute()
        link = file.get('webViewLink')
        print(link)
        print(file_id)
        #return f"https://drive.usercontent.google.com/download?id={file_id}&authuser=0"
        return f"https://drive.google.com/uc?export=view&id={file_id}"

    def upload_and_share(self, file_path, name):

        print(f"📤 Uploading file: {file_path}")
        file_id = self.upload_file(file_path, name)

        print("🔗 Making file public...")
        shareable_link = self.make_file_public(file_id)

        print(f"✅ Done! Shareable link: {shareable_link}")
        return shareable_link
