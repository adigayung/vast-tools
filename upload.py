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

def main():
    parser = argparse.ArgumentParser(
        description="Upload file ZIP ke Hugging Face dataset repo.",
        epilog="Contoh:\n"
               "python upload_hf.py --token=hf_xxx --file=/path/file.zip --repo_id=username/repo-name",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--token", required=True, help="Token HF kamu (hf_...)")
    parser.add_argument("--file", required=True, help="Path file ZIP yang akan diupload")
    parser.add_argument("--repo_id", required=True, help="ID repositori Hugging Face (misal: PapaRazi/id-tts-v2)")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"❌ File tidak ditemukan: {args.file}")
        sys.exit(1)

    try:
        print(f"⬆️  Mengupload {args.file} ke repo {args.repo_id}...")
        upload_file(
            path_or_fileobj=args.file,
            path_in_repo=os.path.basename(args.file),
            repo_id=args.repo_id,
            repo_type="dataset",
            token=args.token
        )
        print("✅ Upload selesai!")
    except Exception as e:
        print(f"❌ Upload gagal: {e}")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("⚠️  Tidak ada argumen diberikan.\n")
        os.system(f"python {sys.argv[0]} --help")
    else:
        main()
