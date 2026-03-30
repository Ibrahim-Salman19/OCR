import threading
import tempfile
import os
from blast_ocr.storage.database import OCRDatabase


def test_manual():
    db_file = tempfile.mktemp(suffix=".db")
    db = OCRDatabase(f"sqlite:///{db_file}")

    session_ids = {}
    lock = threading.Lock()

    def get_session(tid):
        s = db.Session()
        with lock:
            session_ids[tid] = (id(s), type(s).__name__)
        print(f"Thread {tid}: {id(s)} ({type(s)})")
        # Try to use it
        db.create_job(f"file_{tid}.pdf", 1)

    threads = [threading.Thread(target=get_session, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"Session IDs: {session_ids}")
    unique_ids = len(set(sid for sid, _ in session_ids.values()))
    print(f"Unique IDs: {unique_ids}")

    db.close()
    if os.path.exists(db_file):
        os.unlink(db_file)


if __name__ == "__main__":
    test_manual()
