from scripts.GoogleDrive import GoogleDriveService
from reelMaker import POSTS_DIR, GDRIVE_FOLDER_ID
import os

post_number  = 6
local_folder = "D:/CharcterAi/ReelMaker/posts/6"

drive    = GoogleDriveService(None)
drive_id = drive.upload_folder(local_folder, "1O9keZ0tARDgIeTpoRsOm49Eu8EhsBwr8")
print(f"Uploaded -> Drive folder ID: {drive_id}")
