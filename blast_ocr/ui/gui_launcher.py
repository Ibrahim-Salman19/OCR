"""
B.L.A.S.T. Native GUI Launcher
Phase: Deployment (EXE)

Wraps the OCR tools in a Tkinter GUI to be frozen by PyInstaller.
"""
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import sys
import os
import queue

# Import core logic
try:
    from blast_ocr.core.text_extractor import extract_from_pptx, extract_from_pdf, extract_from_image, save_output
except ImportError:
    # Fallback for dev environment if run directly
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'core'))
    from text_extractor import extract_from_pptx, extract_from_pdf, extract_from_image, save_output

class BlastApp:
    def __init__(self, root):
        self.root = root
        self.root.title("B.L.A.S.T. OCR Engine 🚀")
        self.root.geometry("600x450")
        
        # UI Elements
        self.frame = tk.Frame(root, padx=20, pady=20)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        self.lbl_title = tk.Label(self.frame, text="B.L.A.S.T. OCR Automator", font=("Arial", 16, "bold"))
        self.lbl_title.pack(pady=(0, 20))
        
        self.btn_select = tk.Button(self.frame, text="Select Files (PDF, PPTX, Images)", command=self.select_files, height=2, bg="#e1e1e1")
        self.btn_select.pack(fill=tk.X, pady=5)
        
        self.lbl_files = tk.Label(self.frame, text="No files selected", fg="gray")
        self.lbl_files.pack(pady=5)
        
        self.btn_run = tk.Button(self.frame, text="🚀 START PROCESSING", command=self.run_process, state=tk.DISABLED, bg="#4CAF50", fg="white", font=("Arial", 12, "bold"))
        self.btn_run.pack(fill=tk.X, pady=20)
        
        self.log_area = scrolledtext.ScrolledText(self.frame, height=10, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        self.selected_files = []
        self.msg_queue = queue.Queue()
        self.root.after(100, self.process_queue)

    def log(self, message):
        self.msg_queue.put(message)

    def process_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.log_area.config(state='normal')
                self.log_area.insert(tk.END, msg + "\n")
                self.log_area.see(tk.END)
                self.log_area.config(state='disabled')
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def select_files(self):
        files = filedialog.askopenfilenames(title="Select Files", filetypes=[("All Supported", "*.pdf *.pptx *.png *.jpg *.jpeg"), ("PPTX", "*.pptx"), ("PDF", "*.pdf"), ("Images", "*.png;*.jpg")])
        if files:
            self.selected_files = files
            self.lbl_files.config(text=f"{len(files)} files selected")
            self.btn_run.config(state=tk.NORMAL)

    def run_process(self):
        self.btn_run.config(state=tk.DISABLED)
        self.btn_select.config(state=tk.DISABLED)
        self.log("[-] Starting Batch Job...")
        
        # Thread processing to keep UI responsive
        t = threading.Thread(target=self.worker)
        t.start()
        
    def worker(self):
        output_dir = "final_output"
        os.makedirs(output_dir, exist_ok=True)
        
        success_count = 0
        
        for fpath in self.selected_files:
            try:
                fname = os.path.basename(fpath)
                self.log(f"[-] Processing: {fname}")
                
                base_name = os.path.splitext(fname)[0]
                ext = os.path.splitext(fname)[1].lower()
                text = None
                
                # Dynamic Logic
                if ext == ".pptx":
                    from blast_ocr.core.text_extractor import extract_from_pptx
                    text = extract_from_pptx(fpath)
                elif ext == ".pdf":
                    from blast_ocr.core.text_extractor import extract_from_pdf
                    text = extract_from_pdf(fpath)
                else: 
                    from blast_ocr.core.text_extractor import extract_from_image
                    text = extract_from_image(fpath)
                
                if text:
                    from blast_ocr.core.text_extractor import save_output
                    save_output(text, base_name, output_dir)
                    self.log(f"[+] Done: {base_name}")
                    success_count += 1
                else:
                    self.log(f"[!] Warning: No text extracted for {fname}")
                    
            except Exception as e:
                self.log(f"[X] Error on {fpath}: {e}")
        
        self.log("-" * 30)
        self.log(f"Batch Complete. {success_count}/{len(self.selected_files)} processed.")
        self.log(f"Results saved to: {os.path.abspath(output_dir)}")
        
        # Re-enable
        self.root.after(0, lambda: self.btn_run.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.btn_select.config(state=tk.NORMAL))
        self.root.after(0, lambda: messagebox.showinfo("Success", "Processing Complete!"))

if __name__ == "__main__":
    root = tk.Tk()
    app = BlastApp(root)
    root.mainloop()
