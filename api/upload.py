from http.server import BaseHTTPRequestHandler
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import json
import io
import cgi
import os
import time

# --- CONFIGURACIÓN ---
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = '1O_ZkJIeiDTC-9LM_1EXVNOlgYfoRP84u' 

def get_drive_service():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        
        if creds_json:
            # Opción A: JSON Completo (Recomendado)
            service_account_info = json.loads(creds_json)
        else:
            # Opción B: Fallback
            print("Advertencia: Usando variables individuales...")
            private_key = os.environ.get('GOOGLE_PRIVATE_KEY', '')
            if private_key.startswith('"') and private_key.endswith('"'):
                private_key = private_key[1:-1]
            private_key = private_key.replace('\\n', '\n').replace('\\\\n', '\n')
            
            service_account_info = {
                "private_key": private_key,
                "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL'),
                "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
                "token_uri": "https://oauth2.googleapis.com/token",
            }

        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        
        # MANTENEMOS cache_discovery=False para Vercel
        return build('drive', 'v3', credentials=creds, cache_discovery=False)

    except Exception as e:
        print(f"Error CRÍTICO al autenticar: {str(e)}")
        raise e

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_type = self.headers.get('content-type') or ''
            
            # Ajuste de robustez para el formulario
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': content_type}
            )

            file_item = form['photo'] if 'photo' in form else None
            title = form.getvalue('title') or "Sin título"
            latitude = form.getvalue('latitude') or "0.0"
            longitude = form.getvalue('longitude') or "0.0"
            timestamp = int(time.time())

            drive_service = get_drive_service()
            uploaded_files = {}

            # --- SUBIDA DE IMAGEN ---
            # CORRECCIÓN: Quitamos 'resumable=False' para evitar el error "Cannot be converted to bool"
            if file_item and file_item.file:
                file_content = file_item.file.read()
                file_metadata = {'name': f'Reporte_{timestamp}.jpg', 'parents': [FOLDER_ID]}
                
                # Dejamos que MediaIoBaseUpload use su configuración por defecto
                media = MediaIoBaseUpload(io.BytesIO(file_content), mimetype='image/jpeg')
                
                file = drive_service.files().create(
                    body=file_metadata, 
                    media_body=media, 
                    fields='id'
                ).execute()
                uploaded_files['image_id'] = file.get('id')

            # --- SUBIDA DE TEXTO ---
            # CORRECCIÓN: Quitamos 'resumable=False' aquí también
            report_text = f"REPORTE\nTítulo: {title}\nLat: {latitude}\nLon: {longitude}\nImg: Reporte_{timestamp}.jpg"
            txt_metadata = {'name': f'Reporte_{timestamp}.txt', 'parents': [FOLDER_ID]}
            
            txt_media = MediaIoBaseUpload(io.BytesIO(report_text.encode('utf-8')), mimetype='text/plain')
            
            drive_service.files().create(
                body=txt_metadata, 
                media_body=txt_media, 
                fields='id'
            ).execute()

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "files": uploaded_files}).encode('utf-8'))

        except Exception as e:
            print(f"Error en servidor: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode('utf-8'))