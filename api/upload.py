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
    Autentica con Google Drive usando el JSON completo de credenciales.
    """
    try:
        # 1. Intentar leer la variable que tiene TODO el JSON (Recomendado)
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        
        if creds_json:
            # json.loads maneja automáticamente los caracteres especiales
            service_account_info = json.loads(creds_json)
        else:
            # 2. Fallback: Intentar armarlo con variables sueltas (Método antiguo)
            print("Advertencia: Usando variables individuales...")
            private_key = os.environ.get('GOOGLE_PRIVATE_KEY', '')
            
            # Limpieza para evitar errores de formato
            if private_key.startswith('"') and private_key.endswith('"'):
                private_key = private_key[1:-1]
            private_key = private_key.replace('\\n', '\n').replace('\\\\n', '\n')
            
            service_account_info = {
                "private_key": private_key,
                "client_email": os.environ.get('GOOGLE_CLIENT_EMAIL'),
                "project_id": os.environ.get('GOOGLE_PROJECT_ID'),
                "token_uri": "https://oauth2.googleapis.com/token",
            }

        # Crear credenciales
        creds = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=SCOPES
        )
        return build('drive', 'v3', credentials=creds)

    except Exception as e:
        print(f"Error CRÍTICO al autenticar: {str(e)}")
        raise e

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Preparar headers para recibir archivos (multipart/form-data)
            ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
            if ctype == 'multipart/form-data':
                pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
                
            # 2. Procesar el formulario enviado desde Expo
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST',
                         'CONTENT_TYPE': self.headers['Content-Type'],
                         }
            )

            # 3. Extraer datos
            file_item = form['photo'] if 'photo' in form else None
            title = form.getvalue('title') or "Sin título"
            latitude = form.getvalue('latitude') or "0.0"
            longitude = form.getvalue('longitude') or "0.0"
            
            # Generar timestamp (ESTO ERA LO QUE FALLABA ANTES)
            timestamp = int(time.time())

            # 4. Conectar a Google Drive
            drive_service = get_drive_service()
            uploaded_files = {}

            # --- SUBIR LA IMAGEN ---
            if file_item and file_item.file:
                file_content = file_item.file.read()
                
                file_metadata = {
                    'name': f'Reporte_{timestamp}.jpg',
                    'parents': [FOLDER_ID]
                }
                
                media = MediaIoBaseUpload(
                    io.BytesIO(file_content),
                    mimetype='image/jpeg',
                    resumable=True
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
                mimetype='text/plain'
            )
            
            drive_service.files().create(
                body=txt_metadata,
                media_body=txt_media,
                fields='id'
            ).execute()

            # 5. RESPONDER ÉXITO (JSON)
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
            print(f"Error en servidor: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = json.dumps({
                "success": False, 
                "error": str(e)
            })
            self.wfile.write(error_response.encode('utf-8'))