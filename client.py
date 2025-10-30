# File Name : client.py
import sys
import os
import io
import re
import uuid
import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib import request as urllib_request
from urllib import parse as urllib_parse
import base64
import zlib
# External libraries (install if missing)
import importlib
import subprocess
import threading
is_upscale = False

def install_dependencies():
    required_packages = {
        "websocket": "websocket-client",
        "huggingface_hub": "huggingface-hub",
        "pyminizip": "pyminizip",
        "socketio": "python-socketio[client]",
        "requests": "requests",
        "PIL": "Pillow",
        "colorama": "colorama"  # ✅ tambah colorama
    }
    for module_name, pip_name in required_packages.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            print(f"❌ Modul '{module_name}' tidak ditemukan. Menginstal '{pip_name}' ...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])


# Pastikan dependencies terpasang sebelum import
install_dependencies()

import requests
from PIL import Image, PngImagePlugin
from websocket import create_connection, WebSocketException
from colorama import Fore, Style, init
import urllib.request
import urllib.parse

init(autoreset=True)

def get_open_button_token():
    token = os.getenv("OPEN_BUTTON_TOKEN")
    if not token:
        return None
    return token
OPEN_BUTTON_TOKEN = get_open_button_token()

COMFYUI_SERVER = "127.0.0.1:8188"
script_path = os.path.dirname(os.path.abspath(sys.argv[0]))
VASTAI_API_KEY = None
upload_executor = ThreadPoolExecutor(max_workers=4)
WORKFLOW_FILE = "workflow.json"
HOST_MY_PC_LOCAL = "aichanstudio.xyz"

def my_instance_id():
    raw_instance = os.environ.get("VAST_CONTAINERLABEL")  # misal "C.25862941" atau "A.123456"
    if not raw_instance:
        return None
    # Ambil hanya angka dari string
    match = re.search(r'\d+', raw_instance)
    return int(match.group()) if match else None


def delete_workflow_json(file_path):

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"✅ File '{file_path}' berhasil dihapus.")
        except Exception as e:
            print(f"❌ Gagal menghapus '{file_path}': {e}")
    else:
        print(f"ℹ️ File '{file_path}' tidak ditemukan, tidak ada yang dihapus.")


def destroy_instance(instance_id):
    url = f"https://console.vast.ai/api/v0/instances/{instance_id}/"
    if VASTAI_API_KEY:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {VASTAI_API_KEY}"
        }
    else:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    response = requests.delete(url, headers=headers)

    if response.status_code == 200:
        print(f"Instance {instance_id} berhasil dihancurkan.")
        return True
    else:
        print(f"Gagal menghancurkan instance {instance_id}. Status code:", response.status_code)
        print("Response:", response.text)
        return False

def check_comfyui_ready(server_address, check_interval=5):
    """
    Cek apakah server ComfyUI siap menerima request
    Menunggu hingga siap, menampilkan waktu menunggu
    """
    start_time = time.time()
    url = f"http://{server_address}/prompt"  # endpoint yang butuh auth
    headers = {}
    if OPEN_BUTTON_TOKEN:
        headers["Authorization"] = f"Bearer {OPEN_BUTTON_TOKEN}"

    while True:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            elapsed = int(time.time() - start_time)
            m, s = divmod(elapsed, 60)

            if resp.status_code == 200:
                print(f"{Fore.GREEN}✅ ComfyUI ready at {server_address} ({m}m {s}s){Style.RESET_ALL}")
                return True
            elif resp.status_code == 401:
                print(f"{Fore.YELLOW}⚠ ComfyUI not ready (401 Unauthorized). Menunggu... ({m}m {s}s){Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}⚠ ComfyUI not ready (status {resp.status_code}). Menunggu... ({m}m {s}s){Style.RESET_ALL}")
        except requests.exceptions.RequestException as e:
            elapsed = int(time.time() - start_time)
            m, s = divmod(elapsed, 60)
            print(f"{Fore.RED}❌ Error koneksi ke ComfyUI: {e}. Menunggu... ({m}m {s}s){Style.RESET_ALL}")

        time.sleep(check_interval)
    
class LoadWorkFlow:
    def __init__(self, workflow_path=None, workflow_json=None, resolution=None):
        # Load workflow JSON
        if workflow_json is not None:
            json_data = workflow_json
            workflow_path = workflow_path or None
        else:
            if workflow_path is None:
                raise ValueError("Workflow path tidak diberikan dan WORKFLOW_DEFAULT tidak ditemukan di config")
            with open(workflow_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

        self.workflow_json = json_data
        self.workflow_path = workflow_path

        # Resolusi HD
        if resolution == "HD" and "24" in self.workflow_json:
            self.workflow_json["24"]["inputs"]["image"] = ["7", 0]

        # Set model

    # ===== Load workflow dari file JSON =====
    def load_workflow(self, path=None):
        if self.workflow_json is None:
            path = path or self.workflow_path
            with open(path, "r", encoding="utf-8") as f:
                self.workflow_json = json.load(f)
        return self.workflow_json

    # ===== Simpan workflow ke file JSON =====
    def save_workflow(self, path=None):
        path = path or self.workflow_path
        if self.workflow_json is None:
            raise ValueError("Workflow belum di-load")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.workflow_json, f, indent=2)

    # ===== Prompt Handling =====
    def positive_prompt(self, prompt=None):
        if self.workflow_json is None:
            raise ValueError("Workflow belum di-load")
        if prompt is None:
            return self.get_text_by_title("POSITIVE_PROMPT")
        return self.replace_value_by_title("POSITIVE_PROMPT", prompt)

    def negative_prompt(self, prompt=None):
        if self.workflow_json is None:
            raise ValueError("Workflow belum di-load")
        if prompt is None:
            return self.get_text_by_title("NEGATIVE_PROMPT")
        return self.replace_value_by_title("NEGATIVE_PROMPT", prompt)

    # ===== Seed Handling =====
    def seed(self, new_seed=None):
        if self.workflow_json is None:
            raise ValueError("Workflow belum di-load")

        if new_seed is not None:
            replaced = self.replace_easy_seed(self.workflow_json, new_seed)
            if not replaced:
                raise ValueError("Tidak ditemukan node 'easy seed' di workflow")
            return new_seed

        # Ambil seed saat ini
        for node in self.workflow_json.values():
            if node.get("class_type") == "easy seed":
                if "inputs" in node and "seed" in node["inputs"]:
                    return node["inputs"]["seed"]
        raise ValueError("Tidak ditemukan node 'easy seed' di workflow")

    # ===== Model Handling =====
    def model(self, new_model_name=None):
        if self.workflow_json is None:
            raise ValueError("Workflow belum di-load")

        replaced = False
        for node in self.workflow_json.values():
            if node.get("class_type") == "CheckpointLoaderSimple":
                if "inputs" in node and "ckpt_name" in node["inputs"]:
                    if new_model_name is None:
                        return node["inputs"]["ckpt_name"]
                    node["inputs"]["ckpt_name"] = new_model_name
                    replaced = True
                    break
        if not replaced:
            raise ValueError("Tidak ditemukan node 'CheckpointLoaderSimple' di workflow")

    # ===== Ambil workflow JSON =====
    def workflow(self):
        return self.workflow_json

    # ===== Replace value by title (untuk prompt) =====
    def replace_value_by_title(self, title_to_find, new_text):
        node = self.get_node_by_title(title_to_find)
        if node and "inputs" in node:
            node["inputs"]["text"] = new_text
            return True
        return False

    # ===== Ambil teks berdasarkan title =====
    def get_text_by_title(self, title_to_find):
        node = self.get_node_by_title(title_to_find)
        if node:
            return node.get("inputs", {}).get("text")
        return None

    # ===== Cari node berdasarkan _meta['title'] =====
    def get_node_by_title(self, title_to_find):
        for node in self.workflow_json.values():
            if node.get("_meta", {}).get("title") == title_to_find:
                return node
        return None

    # ===== Static method untuk replace seed =====
    @staticmethod
    def replace_easy_seed(workflow, new_seed):
        for node in workflow.values():
            if node.get("class_type") == "easy seed":
                if "inputs" in node and "seed" in node["inputs"]:
                    node["inputs"]["seed"] = new_seed
                    return True
        return False

    # ===== Recursive static method untuk replace value generik =====
    @staticmethod
    def replace_value(obj, old_value, new_value):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    LoadWorkFlow.replace_value(v, old_value, new_value)
                elif v == old_value:
                    obj[k] = new_value
        elif isinstance(obj, list):
            for i in range(len(obj)):
                if isinstance(obj[i], (dict, list)):
                    LoadWorkFlow.replace_value(obj[i], old_value, new_value)
                elif obj[i] == old_value:
                    obj[i] = new_value

class ComfyGenerator:
    def __init__(
        self,
        server_address="127.0.0.1:8188",
        target_folder="./target",
        image_format="JPEG"
    ):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())
        self.target_folder = target_folder
        self.image_format = image_format
        self.workflow = None
        self.ws = None

        if "127.0.0.1" in server_address or "localhost" in server_address:
            self.use_https = False
        else:
            self.use_https = True

        try:
            os.makedirs(target_folder, exist_ok=True)
        except Exception as e:
            raise ConnectionError(f"Error saat membuat folder target: [red]{e}[/red]")
        #print(f"Client ID: [yellow]{self.client_id}[/yellow]", "info")

    # -------------------------------
    # HTTP Helper Functions
    # -------------------------------
    def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(self._http_url("/prompt"), data=data)
        req.add_header("Content-Type", "application/json")
        if OPEN_BUTTON_TOKEN:
            req.add_header("Authorization", f"Bearer {OPEN_BUTTON_TOKEN}")
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        req = urllib.request.Request(self._http_url(f"/view?{url_values}"))
        if OPEN_BUTTON_TOKEN:
            req.add_header("Authorization", f"Bearer {OPEN_BUTTON_TOKEN}")
        with urllib.request.urlopen(req) as response:
            return response.read()

    def get_history(self, prompt_id):
        req = urllib.request.Request(self._http_url(f"/history/{prompt_id}"))
        if OPEN_BUTTON_TOKEN:
            req.add_header("Authorization", f"Bearer {OPEN_BUTTON_TOKEN}")
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read())


    # -------------------------------
    # WebSocket
    # -------------------------------
    def connect_ws(self):
        try:
            headers = []
            if OPEN_BUTTON_TOKEN:
                headers.append(f"Authorization: Bearer {OPEN_BUTTON_TOKEN}")
            self.ws = create_connection(
                self._ws_url(f"/ws?clientId={self.client_id}"),
                header=headers
            )
        except Exception as e:
            raise ConnectionError(f"Error koneksi WebSocket: [red]{e}[/red]")


    # -------------------------------
    # Eksekusi prompt & ambil gambar
    # -------------------------------
    def run_prompt(self, prompt):
        if self.ws is None:
            self.connect_ws()
        self.workflow = prompt
        # Kirim prompt ke server
        prompt_id = self.queue_prompt(prompt)['prompt_id']
        #print(f"Prompt ID: {prompt_id}. Menunggu eksekusi selesai...", "info")

        output_images = {}

        # Tunggu hingga prompt selesai dieksekusi
        while True:
            try:
                out = self.ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message.get('type') == 'executing':
                        data = message.get('data', {})
                        if data.get('node') is None and data.get('prompt_id') == prompt_id:
                            #print(f"Prompt {prompt_id} selesai dieksekusi.", "info")
                            break
            except Exception as e:
                print(f"Error saat menerima data WebSocket: [red]{e}[/red]", "error")
                return None

        # Ambil history
        try:
            history = self.get_history(prompt_id)[prompt_id]
        except Exception as e:
            print(f"Error saat mengambil history: [red]{e}[/red]", "error")
            return None

        # Download semua image
        for node_id, node_output in history['outputs'].items():
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    try:
                        image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                        images_output.append(image_data)
                    except Exception as e:
                        print(f"Error saat mengambil gambar: [red]{e}[/red]", "error")
                output_images[node_id] = images_output

        return output_images

    def _http_url(self, path: str) -> str:
        scheme = "https" if self.use_https else "http"
        return f"{scheme}://{self.server_address}{path}"

    def _ws_url(self, path: str) -> str:
        scheme = "wss" if self.use_https else "ws"
        return f"{scheme}://{self.server_address}{path}"
    # -------------------------------
    # Simpan gambar ke folder target
    # -------------------------------
    def save_images(self, images, img_path="image"):
        saved_files = []
        
        for node_id, img_list in images.items():
            for index, image_data in enumerate(img_list):
                try:
                    image = Image.open(io.BytesIO(image_data))

                    # Convert ke string JSON
                    if isinstance(self.workflow, dict):
                        workflow_str = json.dumps(self.workflow, ensure_ascii=True, separators=(",", ":"))
                    else:
                        workflow_str = str(self.workflow)

                    if self.image_format == "JPEG":
                        file_path = f"{img_path}"
                        image.save(file_path, "JPEG")

                    elif self.image_format == "PNG":
                        file_path = f"{img_path}"
                        meta = PngImagePlugin.PngInfo()
                        meta.add_text("prompt", workflow_str)
                        meta.add_itxt("prompt", workflow_str, lang="", tkey="", zip=False)
                        meta.add_itxt("workflow", workflow_str, lang="", tkey="", zip=False)

                        # Simpan langsung dengan metadata
                        image.save(file_path, "PNG", pnginfo=meta)
                        #print(f"✅ Workflow JSON tersimpan di {file_path}")

                    saved_files.append(file_path)

                except Exception as e:
                    print(f"Error saat menyimpan gambar: {e}", "error")

        return saved_files

    def save_workflow_to_png(image_path, workflow_json, output_path):
        """
        Simpan workflow JSON ke metadata PNG (chunk 'prompt' + 'workflow').
        Ditulis ke tEXt dan iTXt supaya lebih kompatibel dengan ComfyUI.
        """
        img = Image.open(image_path)

        # Convert ke string JSON (jaga kompatibilitas → pakai ensure_ascii=True)
        if isinstance(workflow_json, dict):
            workflow_str = json.dumps(workflow_json, ensure_ascii=True, separators=(",", ":"))
        else:
            workflow_str = str(workflow_json)

        meta = PngImagePlugin.PngInfo()

        # tEXt (Latin-1, basic)
        meta.add_text("prompt", workflow_str)
        #meta.add_text("workflow", workflow_str)

        # iTXt (UTF-8, modern)
        meta.add_itxt("prompt", workflow_str, lang="", tkey="", zip=False)
        meta.add_itxt("workflow", workflow_str, lang="", tkey="", zip=False)

        # Simpan ulang dengan metadata
        img.save(output_path, "PNG", pnginfo=meta)
        print(f"✅ Workflow JSON disimpan di metadata PNG: {output_path}")

    def save_images_HD(self, images, prefix="image"):
        saved_files = []
        os.makedirs(self.target_folder, exist_ok=True)

        for node_id, img_list in images.items():
            for index, image_data in enumerate(img_list):
                try:
                    image = Image.open(io.BytesIO(image_data))
                    if self.image_format.upper() == "JPEG":
                        file_name = f"{prefix}_{node_id}_{uuid.uuid4().hex}_{index + 1}.jpg"
                    else:
                        file_name = f"{prefix}_{node_id}_{uuid.uuid4().hex}_{index + 1}.png"

                    file_path = os.path.join(self.target_folder, file_name)
                    image.save(file_path, self.image_format.upper())
                    saved_files.append(file_path)

                   # print(f"[✓] Hasil Gambar: {file_name}", "success")
                except Exception as e:
                    print(f"Error saat menyimpan gambar: {e}", "error")
        return saved_files
    

my_instance_active = my_instance_id()
if my_instance_active:
    print(f"Instance aktif: {my_instance_active}")
    WORKER_ID = f"VastAi-{my_instance_active}"
else:
    WORKER_ID = f"local-pc"

def decode_workflow_from_zb64(zb64_str: str) -> dict:
    """
    Convert base64 string → decompress → dict
    """
    compressed = base64.b64decode(zb64_str)
    raw = zlib.decompress(compressed).decode("utf-8")
    return json.loads(raw)

def get_image_long_side(image_path):
    img = Image.open(image_path)
    width, height = img.size  # width = lebar, height = tinggi
    longest_side = max(width, height)
    return longest_side

def convert_to_jpg_and_remove(src_path, dest_path):
    img = Image.open(src_path).convert("RGB")  # pastikan RGB untuk JPG
    img.save(dest_path, "JPEG", quality=95)
    os.remove(src_path)

def start_generate_sd():
    job_kosong = False
    all_threads = []
    url_workflow = f"http://{HOST_MY_PC_LOCAL}/vastai_server/get_workflow"

    def upload_image(nomor, filename_only, img_relative_path, job_id):
        try:
            with open(img_relative_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

            upload_payload = {
                "nomor": nomor,
                "WORKER_ID": WORKER_ID,
                "job_id": job_id,
                "filename": filename_only,
                "IMAGE_BASE64": img_b64
            }

            url_receive_files_image = f"http://{HOST_MY_PC_LOCAL}/vastai_server/receive_files_image"
            resp_upload = requests.post(url_receive_files_image, json=upload_payload)

            if resp_upload.status_code == 200:
                print(f"{Fore.CYAN}📁 File Gambar :{Style.RESET_ALL} {Fore.WHITE}{filename_only}{Style.RESET_ALL}")
                print(f"{Fore.GREEN}📤 Upload      : ✅ Berhasil dikirim ke server{Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}📁 File Gambar :{Style.RESET_ALL} {filename_only}")
                print(f"{Fore.RED}📤 Upload      : ❌ Gagal ({resp_upload.status_code}) {resp_upload.text}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[EXCEPTION]{Style.RESET_ALL} Upload gagal:", e)

    # pastikan workflow.txt ada
    if not os.path.exists(WORKFLOW_FILE):
        print(f"{Fore.CYAN}[REQ]{Style.RESET_ALL} Requesting {WORKFLOW_FILE} dari server...")
        try:
            response = requests.get(url_workflow)
            if response.status_code == 200:
                with open(WORKFLOW_FILE, "wb") as f:
                    f.write(response.content)
                print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Workflow berhasil didownload -> {WORKFLOW_FILE}")
            else:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Gagal download workflow ({response.status_code})")
                sys.exit(1)
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Exception saat download workflow:", e)
            sys.exit(1)

    url_get_job = f"http://{HOST_MY_PC_LOCAL}/vastai_server/get_job"
    post_str = {"WORKER_ID": WORKER_ID}

    while not job_kosong:
        try:
            response = requests.post(url_get_job, json=post_str)

            if response.status_code != 200:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Gagal request ({response.status_code}) {response.text}")
                break

            data = response.json()

            # ===================== no job =====================
            if data.get("status") == "empty":
                job_kosong = True
                break

            # ===================== got a job =====================
            if data.get("status") == "ok":
                task = data.get("task", {})

                job_id = task.get("job_id", "")
                text_prompt = task.get("text_prompt", "")
                char_name_input = task.get("char_name_input", "")
                seed = task.get("seed", "")
                nomor = task.get("number", "")

                short_prompt = (text_prompt[:60] + "...") if len(text_prompt) > 60 else text_prompt

                print(f"{Fore.YELLOW}============================================================{Style.RESET_ALL}")
                print(f"{Fore.CYAN}🆔 JOB      :{Style.RESET_ALL} {job_id}  ({nomor})")
                print(f"{Fore.MAGENTA}📜 PROMPT   :{Style.RESET_ALL} {short_prompt}")
                print(f"{Fore.BLUE}👤 CHAR     :{Style.RESET_ALL} {char_name_input}")
                print(f"{Fore.GREEN}🎲 SEED     :{Style.RESET_ALL} {seed}")
                print(f"{Fore.YELLOW}============================================================{Style.RESET_ALL}")

                # ----- generate image -----
                resolution = "SD"
                image_format = "PNG"
                PROJECT_PATH = f"./{char_name_input}"
                os.makedirs(PROJECT_PATH, exist_ok=True)

                wf = LoadWorkFlow(
                    workflow_path=WORKFLOW_FILE,
                    resolution=resolution
                )
                wf.seed(seed)
                wf.positive_prompt(text_prompt)

                cg = ComfyGenerator(
                    server_address=COMFYUI_SERVER,
                    target_folder=PROJECT_PATH,
                    image_format=image_format
                )

                images = cg.run_prompt(wf.workflow())

                if images:
                    filename_only = f"{char_name_input}_{nomor}.png"
                    img_relative_path = os.path.join(PROJECT_PATH, filename_only)
                    cg.save_images(images, img_path=img_relative_path)

                    # ----- Upload di thread terpisah -----
                    proses = threading.Thread(
                        target=upload_image,
                        args=(nomor, filename_only, img_relative_path, job_id),
                        daemon=True  # agar thread tidak mencegah exit program
                    )
                    all_threads.append(proses)
                    proses.start()

                continue

            # ===================== undefined =====================
            print(f"{Fore.RED}[WARN]{Style.RESET_ALL} Response tidak dikenal:", data)
            break

        except Exception as e:
            print(f"{Fore.RED}[EXCEPTION]{Style.RESET_ALL} Error saat request:", e)
            break

    # loop menunggu selesai upload semua
    for proses in all_threads:
        proses.join()
    # ===================== no job =====================
    print(f"{Fore.YELLOW}============================================================{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Tidak ada job lagi (habis).{Style.RESET_ALL}")
    my_instance_active = my_instance_id()
    if my_instance_active:
        destroy_instance(my_instance_active)
        print(f"{Fore.LIGHTRED_EX}🔥 Destroy Vast.AI sukses{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}============================================================{Style.RESET_ALL}")


def start_generate_hd():
    job_kosong = False
    all_threads = []
    url_get_job = f"http://{HOST_MY_PC_LOCAL}/vastai_server/get_job"
    post_str = {"WORKER_ID": WORKER_ID}

    # ----- Nested function: upload HD+SD images -----
    def upload_hd_image(job_id, prefix, file_path_sd, file_path_hd=None):
        try:
            def compress_b64(file_path):
                with open(file_path, "rb") as f:
                    return zlib.compress(f.read())

            img_sd_b64 = base64.b64encode(compress_b64(file_path_sd)).decode("utf-8")
            img_hd_b64 = None
            if file_path_hd and os.path.exists(file_path_hd):
                img_hd_b64 = base64.b64encode(compress_b64(file_path_hd)).decode("utf-8")

            upload_payload = {
                "WORKER_ID": WORKER_ID,
                "job_id": job_id,
                "filename": prefix,
                "IMAGE_SD_BASE64": img_sd_b64,
                "IMAGE_HD_BASE64": img_hd_b64
            }

            url_receive_files_image_hd = f"http://{HOST_MY_PC_LOCAL}/vastai_server/receive_files_image_hd"
            print(f"{Fore.CYAN}📤 Uploading SD+HD images to server...{Style.RESET_ALL}")
            resp_upload = requests.post(url_receive_files_image_hd, json=upload_payload)

            if resp_upload.status_code == 200:
                print(f"{Fore.GREEN}✅ Upload successful: SD+HD images sent!{Style.RESET_ALL}")
                print(f"{Fore.GREEN}SD Path:{Style.RESET_ALL} {file_path_sd}")
                if file_path_hd:
                    print(f"{Fore.GREEN}HD Path:{Style.RESET_ALL} {file_path_hd}")
                print(f"{Fore.YELLOW}{'-'*50}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Upload failed: {resp_upload.status_code} {resp_upload.text}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[EXCEPTION]{Style.RESET_ALL} Upload failed:", e)

    while not job_kosong:
        try:
            print(f"{Fore.CYAN}🌐 Requesting job from server...{Style.RESET_ALL}")
            response = requests.post(url_get_job, json=post_str)
            if response.status_code != 200:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Gagal request ({response.status_code}) {response.text}")
                break

            data = response.json()

            # ===================== no job =====================
            if data.get("status") == "empty":
                job_kosong = True
                break

            # ===================== got a job =====================
            print(f"{Fore.CYAN}🔹 Job received:{Style.RESET_ALL}")
            task = data.get("task", {})
            job_id = task.get("job_id")
            nomor = task.get("number")
            prefix_path = task.get("png_file")

            WORKFLOW_RAW = data.get("WORKFLOW")
            WORKFLOW_DICT = decode_workflow_from_zb64(WORKFLOW_RAW)
            prefix = os.path.splitext(os.path.basename(prefix_path))[0]

            print(f"{Fore.CYAN}Number       :{Style.RESET_ALL} {nomor}")
            print(f"{Fore.CYAN}Job ID       :{Style.RESET_ALL} {job_id}")
            print(f"{Fore.CYAN}File to HD   :{Style.RESET_ALL} {prefix_path}")
            print(f"{Fore.CYAN}Prefix       :{Style.RESET_ALL} {prefix}")

            wf = LoadWorkFlow(workflow_json=WORKFLOW_DICT, resolution="HD")
            cg = ComfyGenerator(server_address=COMFYUI_SERVER, target_folder=script_path, image_format="PNG")

            print(f"{Fore.CYAN}🖌 Generating HD images...{Style.RESET_ALL}")
            images = cg.run_prompt(wf.workflow())

            if not images:
                print(f"{Fore.RED}❌ Tidak ada gambar dihasilkan.{Style.RESET_ALL}")
                continue

            # Save HD & SD
            file_cg = cg.save_images_HD(images, prefix=prefix)
            sd_folder = os.path.join(script_path, "sd")
            hd_folder = os.path.join(script_path, "hd")
            os.makedirs(sd_folder, exist_ok=True)
            os.makedirs(hd_folder, exist_ok=True)

            file_path_sd, file_path_hd = None, None
            if len(file_cg) >= 2:
                is_hd_img = get_image_long_side(file_cg[0]) > get_image_long_side(file_cg[1])
                file_path_sd = os.path.join(sd_folder, f"{prefix}_SD.jpg")
                file_path_hd = os.path.join(hd_folder, f"{prefix}_HD.jpg")
                if is_hd_img:
                    convert_to_jpg_and_remove(file_cg[1], file_path_sd)
                    convert_to_jpg_and_remove(file_cg[0], file_path_hd)
                else:
                    convert_to_jpg_and_remove(file_cg[0], file_path_sd)
                    convert_to_jpg_and_remove(file_cg[1], file_path_hd)
            elif len(file_cg) == 1:
                file_path_sd = os.path.join(sd_folder, f"{prefix}_SD.jpg")
                convert_to_jpg_and_remove(file_cg[0], file_path_sd)

            # ----- Upload di thread terpisah -----
            proses = threading.Thread(
                target=upload_hd_image,
                args=(job_id, prefix, file_path_sd, file_path_hd),
                daemon=True
            )
            all_threads.append(proses)
            proses.start()

        except Exception as e:
            print(f"{Fore.RED}[EXCEPTION]{Style.RESET_ALL} Error saat request:", e)
            break

    # ===================== no job =====================
    for proses in all_threads:
        proses.join()
    print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Tidak ada job lagi (habis).{Style.RESET_ALL}")
    my_instance_active = my_instance_id()
    if my_instance_active:
        destroy_instance(my_instance_active)
        print(f"{Fore.LIGHTRED_EX}🔥 Vast.AI instance destroyed{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")

def start():
    global is_upscale
    url_generate_type = f"http://{HOST_MY_PC_LOCAL}/vastai_server/generate_type"
    payload = {"is_upscale": is_upscale}

    try:
        response = requests.post(url_generate_type, json=payload)
        if response.status_code == 200:
            data = response.json()  # ambil response JSON dari server
            # print("Response:", data)

            # baca nilai is_upscale dari server
            server_is_upscale = data.get("is_upscale", False)

            if server_is_upscale:
                print("Upscale mode ON → jalankan proses upscale")
                start_generate_hd()
            else:
                print("Upscale mode OFF → jalankan proses normal")
                start_generate_sd()
        else:
            print("Gagal request:", response.status_code, response.text)
    except Exception as e:
        print("Error saat request:", e)

    return

# ---------------- MAIN ----------------
if __name__ == "__main__":
    # baca API key dari argumen command line
    delete_workflow_json(WORKFLOW_FILE)
    for arg in sys.argv[1:]:
        if arg.startswith("API="):
            VASTAI_API_KEY = arg.split("=", 1)[1]
            break

    check_comfyui_ready(COMFYUI_SERVER)
    print(f"{Fore.GREEN}✅ ComfyUI siap, mulai generate HD...{Style.RESET_ALL}")
    start()