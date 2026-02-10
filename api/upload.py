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
    """
    Autentica con Google Drive usando el JSON completo.
    IMPORTANTE: cache_discovery=False es vital en Vercel.
    """
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        
        if creds_json:
            # Opción A: JSON Completo (Recomendado)
            service_account_info = json.loads(creds_json)
        else:
            # Opción B: Fallback (Solo si no has configurado el JSON completo)
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
        
        # --- CORRECCIÓN CLAVE AQUÍ ---
        # cache_discovery=False evita el error "file_cache" y "Cannot be converted to bool"
        # en entornos serverless donde no se puede escribir en disco.
        return build('drive', 'v3', credentials=creds, cache_discovery=False)

    except Exception as e:
        print(f"Error CRÍTICO al autenticar: {str(e)}")
        raise e

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Parsear el Content-Type correctamente
            content_type = self.headers.get('content-type') or ''
            
            # 2. Procesar el formulario (Compatible con Serverless)
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': content_type,
                }
            )

            # 3. Extraer datos con valores por defecto seguros
            file_item = form['photo'] if 'photo' in form else None
            title = form.getvalue('title') or "Sin título"
            latitude = form.getvalue('latitude') or "0.0"
            longitude = form.getvalue('longitude') or "0.0"
            
            timestamp = int(time.time())

            # 4. Conectar a Drive
            drive_service = get_drive_service()
            uploaded_files = {}

            # --- SUBIR LA IMAGEN ---
            # Usamos resumable=False para mayor estabilidad en archivos pequeños (<5MB)
            if file_item and file_item.file:
                file_content = file_item.file.read()
                
                file_metadata = {
                    'name': f'Reporte_{timestamp}.jpg',
                    'parents': [FOLDER_ID]
                }
                
                media = MediaIoBaseUpload(
                    io.BytesIO(file_content),
                    mimetype='image/jpeg',
                    resumable=False 
                )
                
                file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                uploaded_files['image_id'] = file.get('id')

            # --- SUBIR EL TEXTO ---
            report_text = f"REPORTE DE INCIDENTE\n--------------------\nTítulo: {title}\nLatitud: {latitude}\nLongitud: {longitude}\nReferencia Imagen: Reporte_{timestamp}.jpg"
            
            txt_metadata = {
                'name': f'Reporte_{timestamp}.txt',
                'parents': [FOLDER_ID]
            }
            
            txt_media = MediaIoBaseUpload(
                io.BytesIO(report_text.encode('utf-8')),
                mimetype='text/plain',
                resumable=False
            )
            
            drive_service.files().create(
                body=txt_metadata,
                media_body=txt_media,
                fields='id'
            ).execute()

            # 5. RESPONDER ÉXITO
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response_data = json.dumps({
                "success": True, 
                "message": "Reporte subido correctamente",
                "files": uploaded_files
            })
            self.wfile.write(response_data.encode('utf-8'))

        except Exception as e:
            # 6. MANEJO DE ERRORES
            # Imprimimos el error en los logs de Vercel
            print(f"Error en servidor: {str(e)}")
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = json.dumps({
                "success": False, 
                "error": str(e)
            })
            self.wfile.write(error_response.encode('utf-8'))