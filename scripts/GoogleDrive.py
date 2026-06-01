import os
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class GoogleDriveService:
    SCOPES = ["https://www.googleapis.com/auth/drive"]

    def __init__(self, credentials_file=None):
        if credentials_file is None:
            credentials_file = "D:/CharcterAi/ReelMaker/scripts/auth.json"

        self.token_file = "D:/CharcterAi/ReelMaker/scripts/token.pickle"

        creds = None

        # Load saved token
        if os.path.exists(self.token_file):
            with open(self.token_file, "rb") as token:
                creds = pickle.load(token)

        # Login or refresh token
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file,
                    self.SCOPES
                )

                creds = flow.run_local_server(port=0)

            with open(self.token_file, "wb") as token:
                pickle.dump(creds, token)

        self.service = build("drive", "v3", credentials=creds)

    def create_folder(self, folder_name, parent_folder_id):
        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id]
        }

        folder = self.service.files().create(
            body=metadata,
            fields="id,name"
        ).execute()

        print(f"Created folder: {folder['name']}")

        return folder["id"]

    def upload_file(self, file_path, parent_folder_id):
        metadata = {
            "name": os.path.basename(file_path),
            "parents": [parent_folder_id]
        }

        media = MediaFileUpload(
            file_path,
            resumable=True
        )

        uploaded_file = self.service.files().create(
            body=metadata,
            media_body=media,
            fields="id,name"
        ).execute()

        print(f"Uploaded: {uploaded_file['name']}")

        return uploaded_file["id"]

    def upload_folder(self, local_folder, parent_folder_id):
        folder_name = os.path.basename(
            os.path.normpath(local_folder)
        )

        drive_folder_id = self.create_folder(
            folder_name,
            parent_folder_id
        )

        for item in os.listdir(local_folder):
            item_path = os.path.join(local_folder, item)

            if os.path.isfile(item_path):
                self.upload_file(
                    item_path,
                    drive_folder_id
                )

            elif os.path.isdir(item_path):
                self.upload_folder(
                    item_path,
                    drive_folder_id
                )

        return drive_folder_id


if __name__ == "__main__":
    DRIVE_FOLDER_ID = "1O9keZ0tARDgIeTpoRsOm49Eu8EhsBwr8"

    drive = GoogleDriveService(
        "D:/CharcterAi/ReelMaker/scripts/auth.json"
    )

    # Upload a single file
    # drive.upload_file(
    #     "D:/videos/reel.mp4",
    #     DRIVE_FOLDER_ID
    # )

    # Upload a folder
    drive.upload_folder(
        "D:/videos",
        DRIVE_FOLDER_ID
    )

    print("Upload completed.")