from http.server import BaseHTTPRequestHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json, io, time, cgi, os

# --- CONFIGURACIÓN ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
# Usando el ID de carpeta confirmado: 1O_ZkJIeiDTC-9LM_1EXVNOlgYfoRP84u
FOLDER_ID = '1O_ZkJIeiDTC-9LM_1EXVNOlgYfoRP84u' 

def get_drive_service():
    """Configura las credenciales usando variables de entorno de Vercel."""
    # Obtenemos la llave privada y corregimos los saltos de línea (\n)
    private_key = os.environ.get('GOOGLE_PRIVATE_KEY', '')
    if private_key:
        # Esto elimina el error "Unable to load PEM file" al convertir \n texto en saltos reales
        private_key = private_key.replace('\\n', '\n')

    service_account_info = {
        "type": "service_account",
        "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
        "private_key": private_key,
        "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL'),
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        """Manejo de CORS para peticiones desde el App."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_POST(self):
        try:
            # Inicializar el servicio de Google Drive
            drive_service = get_drive_service()

            # Leer y parsear el contenido multipart (imagen y datos)
            content_type = self.headers.get('Content-Type')
            ctype, pdict = cgi.parse_header(content_type)
            
            pdict['boundary'] = bytes(pdict['boundary'], 'utf-8')
            pdict['CONTENT-LENGTH'] = int(self.headers.get('Content-Length', 0))

            fields = cgi.parse_multipart(self.rfile, pdict)

            # Extraer campos enviados desde ReportForm.tsx
            photo_data = fields.get('photo')[0]
            title      = fields.get('title', ['Sin título'])[0]
            address    = fields.get('address', ['Sin dirección'])[0]
            date       = fields.get('date', [''])[0]
            time_val   = fields.get('time', [''])[0]
            latitude   = fields.get('latitude', ['0'])[0]
            longitude  = fields.get('longitude', ['0'])[0]

            timestamp = int(time.time())

            # 1. Subir la imagen WebP a la carpeta específica
            file_metadata = {
                'name': f'Reporte_{timestamp}.webp',
                'parents': [FOLDER_ID],
                'description': f'Título: {title} | Dir: {address} | Coords: {latitude}, {longitude}'
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

            # 2. Crear un archivo de texto con el resumen del incidente
            report_text = f"""REPORTE DE INCIDENTE
====================
Título:    {title}
Dirección: {address}
Fecha:     {date}
Hora:      {time_val}
Latitud:   {latitude}
Longitud:  {longitude}
Imagen:    Reporte_{timestamp}.webp
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

            # Enviar respuesta de éxito en JSON para que el App lo reciba correctamente
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
            # Capturar cualquier error y devolverlo como JSON para evitar SyntaxError en Expo
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'error': str(e)
            }).encode())