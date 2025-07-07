# Auto-install huggingface_hub jika belum ada
try:
    from huggingface_hub import upload_file
except ImportError:
    import subprocess
    import sys
    print("📦 huggingface_hub belum terinstall. Menginstall terlebih dahulu...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "huggingface_hub"])
    from huggingface_hub import upload_file

import argparse
import os
import sys
import shutil

def zip_folder(folder_path):
    zip_path = f"{folder_path.rstrip(os.sep)}.zip"
    shutil.make_archive(base_name=folder_path, format="zip", root_dir=folder_path)
    return zip_path

def main():
    parser = argparse.ArgumentParser(
        description="""
📤 Upload file ZIP atau folder ke Hugging Face repo (dataset atau model).

Gunakan salah satu dari:
- --file: jika sudah punya file .zip yang siap upload
- --path2zip: jika ingin upload folder (akan di-zip otomatis)

""",
        epilog="""
🔧 ARGUMEN LENGKAP:

--token           🔐 Token akses Hugging Face kamu (hf_...).
--file            📦 Path file ZIP yang akan diupload langsung.
--path2zip        📁 Path folder yang akan di-zip dan diupload.
--auto-del-path   🧨 Jika 'yes', folder sumber akan dihapus setelah upload (default: no).
--repo_id         📂 ID repositori tujuan di Hugging Face (misal: PapaRazi/id-tts-v2).
--repo_type       🏷️  Jenis repo: dataset atau model (default: dataset).

💡 CONTOH PENGGUNAAN:

1. Upload file ZIP:
   python upload.py --token=hf_abc123 --file=/path/file.zip --repo_id=username/repo --repo_type=dataset

2. Upload folder, auto-zip:
   python upload.py --token=hf_abc123 --path2zip=/data/folder --repo_id=username/repo --repo_type=dataset

3. Upload folder dan hapus sumber:
   python upload.py --token=hf_abc123 --path2zip=/data/folder --repo_id=username/repo --repo_type=dataset --auto-del-path=yes
""",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("--token", required=True, help="Token HF kamu (hf_...)")
    parser.add_argument("--file", help="Path file ZIP yang akan diupload")
    parser.add_argument("--path2zip", help="Path folder yang akan di-zip lalu diupload")
    parser.add_argument("--auto-del-path", choices=["yes", "no"], default="no",
                        help="Jika 'yes', folder --path2zip akan dihapus setelah upload (default: no)")
    parser.add_argument("--repo_id", required=True, help="ID repositori HF (misal: PapaRazi/id-tts-v2)")
    parser.add_argument("--repo_type", default="dataset", choices=["dataset", "model"],
                        help="Jenis repositori: 'dataset' atau 'model' (default: dataset)")

    args = parser.parse_args()

    # Validasi penggunaan path2zip
    if not args.file and not args.path2zip:
        print("❌ Harus menggunakan --file atau --path2zip.")
        sys.exit(1)

    cleanup_zip = False
    cleanup_folder = False

    if args.path2zip:
        if not os.path.isdir(args.path2zip):
            print(f"❌ Folder tidak ditemukan: {args.path2zip}")
            sys.exit(1)
        print(f"🗜️  Membuat ZIP dari folder: {args.path2zip}")
        args.file = zip_folder(args.path2zip)
        cleanup_zip = True
        if args.auto_del_path == "yes":
            cleanup_folder = True

    if not os.path.isfile(args.file):
        print(f"❌ File tidak ditemukan: {args.file}")
        sys.exit(1)

    try:
        print(f"⬆️  Mengupload {args.file} ke repo {args.repo_id} ({args.repo_type})...")
        url = upload_file(
            path_or_fileobj=args.file,
            path_in_repo=os.path.basename(args.file),
            repo_id=args.repo_id,
            repo_type=args.repo_type,
            token=args.token
        )
        print(f"✅ Upload selesai!")
        print(f"🔗 File tersedia di:\n{url}")
    except Exception as e:
        print(f"❌ Upload gagal: {e}")
    finally:
        if cleanup_zip:
            try:
                os.remove(args.file)
                print(f"🧹 File ZIP sementara dihapus: {args.file}")
            except Exception as e:
                print(f"⚠️ Gagal menghapus ZIP sementara: {e}")
        if cleanup_folder:
            try:
                shutil.rmtree(args.path2zip)
                print(f"🧨 Folder sumber dihapus: {args.path2zip}")
            except Exception as e:
                print(f"⚠️ Gagal menghapus folder sumber: {e}")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("⚠️  Tidak ada argumen diberikan.\n")
        os.system(f"python {sys.argv[0]} --help")
    else:
        main()
