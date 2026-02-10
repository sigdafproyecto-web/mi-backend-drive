from http.server import BaseHTTPRequestHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json, io, time, cgi, os

# Configuración Constante
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = '1O_ZkJIeiDTC-9LM_1EXVNOlgYfoRP84u'  

def get_drive_service():
    # Construimos el diccionario de credenciales usando tus variables de Vercel
    # El replace es vital para que la llave privada sea válida
    service_account_info = {
        "type": "service_account",
        "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
        "private_key": os.environ.get('GOOGLE_PRIVATE_KEY', '').replace('\\n', '\n'),
        "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL'),
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_POST(self):
        try:
            # Inicializar servicio de Drive
            drive_service = get_drive_service()

            content_type = self.headers.get('Content-Type')
            ctype, pdict = cgi.parse_header(content_type)
            
            # Preparación para parsear multipart
            pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers.get('Content-Length', 0))

            fields = cgi.parse_multipart(self.rfile, pdict)

            # Extraer datos del formulario
            photo_data = fields.get('photo')[0]
            title      = fields.get('title', ['Sin título'])[0]
            address    = fields.get('address', ['Sin dirección'])[0]
            date       = fields.get('date', [''])[0]
            time_val   = fields.get('time', [''])[0]
            latitude   = fields.get('latitude', ['0'])[0]
            longitude  = fields.get('longitude', ['0'])[0]

            timestamp = int(time.time())

            # 1. Subir la imagen a Drive usando el FOLDER_ID corregido
            file_metadata = {
                'name': f'Reporte_{timestamp}.webp',
                'parents': [FOLDER_ID],
                'description': f'Título: {title} | Dirección: {address} | Ubicación: {latitude}, {longitude}'
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

            # 2. Crear archivo .txt con detalles del reporte
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

            # Respuesta exitosa en JSON para evitar errores en el App
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
            # Si algo falla, devolvemos el error como JSON para que Expo lo lea bien
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())