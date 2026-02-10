from http.server import BaseHTTPRequestHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json, io, time, cgi, os

SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = 'TU_FOLDER_ID'  # Lo configuramos después

service_account_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_type = self.headers.get('Content-Type')
            ctype, pdict = cgi.parse_header(content_type)
            pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
            
            fields = cgi.parse_multipart(self.rfile, pdict)
            photo_data = fields.get('photo')[0]

            file_metadata = {
                'name': f'foto_{int(time.time())}.jpg',
                'parents': [FOLDER_ID]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(photo_data),
                mimetype='image/jpeg'
            )
            
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'fileId': file.get('id')
            }).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e)
            }).encode())