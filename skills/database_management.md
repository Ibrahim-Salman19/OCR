---
name: Database Management
description: Guide to managing the SQLite database and SQLAlchemy ORM in B.L.A.S.T.
---

# Database Management Skill

## 1. Architecture
The project uses **SQLAlchemy** (ORM) with **SQLite**.
- **Location**: `blast_ocr.db` (root directory).
- **Code**: `blast_ocr/storage/database.py`.

## 2. Schema
### `OCRJob`
Tracks the overall file processing task.
- `id`: Primary Key
- `filename`: Source file name
- `status`: 'pending', 'processing', 'completed', 'failed'
- `error_message`: Stores failure reason

### `OCRResult`
Stores per-page results.
- `job_id`: FK to `OCRJob`
- `extracted_text`: Raw text
- `confidence_score`: 0.0 to 1.0 float

## 3. Common Operations

### CLI / Script Access
```python
from blast_ocr.storage.database import OCRDatabase

db = OCRDatabase()
# Get all failed jobs
failed_jobs = db.session.query(OCRJob).filter_by(status='failed').all()
```

### Migrations
Currently, `Base.metadata.create_all(self.engine)` is run on init.
- **Adding Columns**: No automatic migration tool (Alembic) is configured yet.
- **Workflow**: For schema changes, either:
  1. Delete `blast_ocr.db` (if data is disposable).
  2. Manually execute `ALTER TABLE` commands via SQLite CLI.

## 4. Best Practices
- **Session Management**: Always close sessions. Use the context manager pattern if extending `OCRDatabase` to support it (currently uses `__del__` backup).
- **Concurrency**: SQLite writes verify serialization. The `BlastPipeline` handles this by writing to DB only from the main thread.
