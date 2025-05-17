import os
import requests
import json
import logging
import time
from dotenv import load_dotenv
from pathlib import Path
import urllib.parse
from flask import Flask, send_from_directory

# Initialize Flask app
app = Flask(__name__)

# Setup logging
logging.basicConfig(
    filename='upload.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()
USERNAME = os.getenv('API_USERNAME', 'topik')
PASSWORD = os.getenv('API_PASSWORD', 'topik')
BASE_URL = os.getenv('RENDER_BASE_URL')  # Misalnya, https://your-backend.onrender.com
UPLOAD_PHP_URL = 'https://inhua.ct.ws/admin/upload.php'

# Pastikan RENDER_BASE_URL diset
if not BASE_URL:
    logging.error("RENDER_BASE_URL tidak diset di .env")
    raise ValueError("RENDER_BASE_URL harus diset di .env")

# Folder untuk file JSON
PUBLIC_DIR = Path('temp')
PUBLIC_DIR.mkdir(exist_ok=True)

# Flask route untuk menyajikan file JSON secara publik
@app.route('/temp/<path:filename>')
def serve_temp(filename):
    try:
        return send_from_directory(PUBLIC_DIR, filename)
    except Exception as e:
        logging.error(f"Error serving file {filename}: {e}")
        return {"error": f"File not found or inaccessible: {filename}"}, 404

def trigger_upload(json_file):
    """Mengirim GET request ke upload.php untuk satu file JSON."""
    if not json_file or not json_file.exists():
        logging.error(f"File JSON tidak ditemukan: {json_file}")
        print(f"Error: File JSON tidak ditemukan: {json_file}")
        return False

    # Buat URL publik untuk file JSON
    json_url = f"{BASE_URL}/temp/{json_file.name}"
    
    # Siapkan parameter untuk GET request
    params = {
        'url': json_url,
        'username': USERNAME,
        'password': PASSWORD
    }
    
    # Encode parameter URL
    encoded_url = f"{UPLOAD_PHP_URL}?{urllib.parse.urlencode(params)}"

    # Header untuk meniru browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9'
    }

    try:
        logging.info(f"Mengirim GET request ke {encoded_url}")
        # Gunakan session untuk mengontrol redirect
        session = requests.Session()
        session.max_redirects = 10  # Batasi redirect
        response = session.get(
            encoded_url,
            headers=headers,
            timeout=30,
            verify=True,  # Gunakan SSL verification untuk produksi
            allow_redirects=True
        )
        logging.info(f"Status code respons: {response.status_code}")
        logging.info(f"Header respons: {response.headers}")
        logging.info(f"Riwayat redirect: {[r.url for r in response.history]}")
        logging.info(f"Isi respons: {response.text[:1000]}")

        if response.status_code != 200:
            logging.error(f"HTTP error: Status {response.status_code}, Respons: {response.text[:1000]}")
            print(f"Error: HTTP {response.status_code} - {response.text[:1000]}")
            return False

        try:
            result = response.json()
            status = result.get('status')
            message = result.get('message')
            total_inserted = result.get('total_inserted', 0)
            total_skipped = result.get('total_skipped', 0)
            total_failed = result.get('total_failed', 0)
            files_info = result.get('files', [])

            if status == 'success':
                logging.info(f"Upload berhasil: {message}")
                print(f"Sukses: {message}")
                print(f"Inserted: {total_inserted}, Skipped: {total_skipped}, Failed: {total_failed}")
                for file_info in files_info:
                    print(f"File: {file_info['file']}, Status: {file_info['status']}, "
                          f"Inserted: {file_info['inserted']}, Skipped: {file_info['skipped']}, "
                          f"Failed: {file_info['failed']}")
                    if file_info['errors']:
                        print(f"Errors: {'; '.join(file_info['errors'])}")
                return True
            else:
                logging.error(f"Upload gagal: {message}")
                print(f"Error: {message}")
                if files_info:
                    for file_info in files_info:
                        if file_info['errors']:
                            print(f"File: {file_info['file']}, Errors: {'; '.join(file_info['errors'])}")
                return False

        except ValueError:
            logging.error(f"Respons JSON tidak valid: {response.text[:1000]}")
            print(f"Error: Respons server tidak valid - {response.text[:1000]}")
            return False

    except requests.exceptions.TooManyRedirects as e:
        logging.error(f"Terlalu banyak redirect: {e}")
        logging.info(f"Riwayat redirect: {[r.url for r in e.response.history]}")
        print(f"Error: Terlalu banyak redirect - {e}")
        return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error request: {e}")
        print(f"Error: {e}")
        return False

def main():
    # Dapatkan daftar file JSON di folder temp/
    json_files = list(PUBLIC_DIR.glob('*.json'))
    if not json_files:
        logging.error("Tidak ada file JSON di folder temp")
        print("Error: Tidak ada file JSON di folder temp")
        return

    logging.info(f"Ditemukan {len(json_files)} file JSON: {[f.name for f in json_files]}")
    print(f"Ditemukan {len(json_files)} file JSON: {[f.name for f in json_files]}")

    # Proses setiap file JSON satu per satu
    for json_file in json_files:
        print(f"Memproses file: {json_file.name}")
        success = trigger_upload(json_file)
        if success:
            logging.info("Menunggu 60 detik sebelum memproses file berikutnya")
            print("Menunggu 60 detik sebelum memproses file berikutnya...")
            time.sleep(60)  # Jeda 1 menit setelah sukses

if __name__ == "__main__":
    # Jalankan Flask app
    port = int(os.getenv('PORT', 10000))  # Default port Render.com
    app.run(host='0.0.0.0', port=port, debug=False)