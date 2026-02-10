from http.server import BaseHTTPRequestHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json, io, time, cgi, os

SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = 'Reportes'  

service_account_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
credentials = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=credentials)

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_POST(self):
        try:
            content_type = self.headers.get('Content-Type')
            ctype, pdict = cgi.parse_header(content_type)
            pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])

            fields = cgi.parse_multipart(self.rfile, pdict)

            # Datos del reporte
            photo_data = fields.get('photo')[0]
            title     = fields.get('title', ['Sin título'])[0]
            address   = fields.get('address', ['Sin dirección'])[0]
            date      = fields.get('date', [''])[0]
            time_val  = fields.get('time', [''])[0]
            latitude  = fields.get('latitude', ['0'])[0]
            longitude = fields.get('longitude', ['0'])[0]

            timestamp = int(time.time())

            # 1. Subir la imagen a Drive
            file_metadata = {
                'name': f'Reporte_{timestamp}.webp',
                'parents': [FOLDER_ID],
                'description': f'Título: {title} | Dirección: {address} | Fecha: {date} {time_val} | Lat: {latitude} | Lon: {longitude}'
            }

            media = MediaIoBaseUpload(
                io.BytesIO(photo_data),
                mimetype='image/webp'
            )

            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            ).execute()

            # 2. También crear un archivo .txt con los datos del reporte
            report_text = f"""REPORTE DE INCIDENTE
====================
Título:    {title}
Dirección: {address}
Fecha:     {date}
Hora:      {time_val}
Latitud:   {latitude}
Longitud:  {longitude}
Archivo:   Reporte_{timestamp}.webp
"""
            txt_metadata = {
                'name': f'Reporte_{timestamp}.txt',
                'parents': [FOLDER_ID],
            }

            txt_media = MediaIoBaseUpload(
                io.BytesIO(report_text.encode('utf-8')),
                mimetype='text/plain'
            )

            drive_service.files().create(
                body=txt_metadata,
                media_body=txt_media,
                fields='id'
            ).execute()

            # Responder éxito
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'fileId': file.get('id'),
                'fileName': file.get('name')
            }).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': str(e)
            }).encode())