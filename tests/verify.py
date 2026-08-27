import os
from PIL import Image, ImageDraw
from blast_ocr.main import BlastPipeline
import time


def create_test_image(text="Hello World B.L.A.S.T.", filename="test_verify.png"):
    img = Image.new("RGB", (800, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Use default font
    d.text((10, 10), text, fill=(0, 0, 0))
    img.save(filename)
    return filename


def verify():
    print("[-] Creating test image...")
    img_path = create_test_image()

    print("[-] Initializing Pipeline...")
    pipeline = BlastPipeline()

    output_dir = "verify_output"
    if os.path.exists(output_dir):
        import shutil

        shutil.rmtree(output_dir)

    print(f"[-] Processing {img_path}...")
    time.time()
    result = pipeline.process_job(img_path, output_dir=output_dir)
    time.time()

    print(f"[-] Result: {result}")

    if result["status"] == "success":
        print("[+] Success!")
        md_path = result["output_files"]["md"]
        if os.path.exists(md_path):
            with open(md_path, "r") as f:
                content = f.read()
                print(f"[-] Extracted Content: {content.strip()}")
                if "Hello" in content or "World" in content:
                    print("[+] Content verification passed.")
                else:
                    print(
                        "[!] Content verification FAILED (OCR quality issue or empty)."
                    )
        else:
            print("[!] Markdown output missing.")
    else:
        print(f"[!] Processing FAILED: {result.get('error')}")

    # Clean up
    if os.path.exists(img_path):
        os.remove(img_path)
    # shutil.rmtree(output_dir) # Keep for inspection if needed


if __name__ == "__main__":
    verify()
