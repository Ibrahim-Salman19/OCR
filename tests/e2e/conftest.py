"""
tests/e2e/conftest.py

Shared fixtures for B.L.A.S.T. OCR End-to-End Test Suite.
Provides synthetic multi-page document generators, in-memory Redis,
FastAPI test client, mock S3/local storage backends, and ONNX Runtime mocks.
"""

import io
import os
import json
import time
import uuid
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import MagicMock, patch

import pytest
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import fakeredis
    HAS_FAKEREDIS = True
except ImportError:
    HAS_FAKEREDIS = False

try:
    from fastapi.testclient import TestClient
    from blast_ocr.api.app import app as fastapi_app
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@pytest.fixture(autouse=True)
def mock_easyocr_reader_for_tests():
    """No-op override of root conftest easyocr patch to avoid slow torch import in e2e tests."""
    yield


@pytest.fixture(autouse=True)
def auto_patch_redis(mock_redis):
    """No-op / isolated override of root conftest auto_patch_redis for e2e tests."""
    yield



# ============================================================================
# 1. Synthetic Multi-Page Image / PDF Document Generators
# ============================================================================

@pytest.fixture
def synthetic_pdf_generator():
    """
    Factory fixture returning a callable to generate multi-page PDF bytes
    with customizable page count, dimensions, text content, and DPI.
    """
    def _generator(
        page_count: int = 3,
        width: int = 595,
        height: int = 842,
        text_prefix: str = "B.L.A.S.T. OCR Test Page",
        font_size: int = 14,
    ) -> bytes:
        if HAS_FITZ:
            doc = fitz.open()
            for i in range(page_count):
                page = doc.new_page(width=width, height=height)
                page.insert_text(
                    (50, 72),
                    f"{text_prefix} #{i + 1}\nDeterministic Pipeline Verification\nBatch Index: {i}",
                    fontsize=font_size,
                )
                # Draw a rectangle box to simulate bounding box detection targets
                rect = fitz.Rect(50, 150, width - 50, 250)
                page.draw_rect(rect, color=(0, 0, 1), width=1.5)
                page.insert_text((60, 200), f"Sample content line {i+1} for OCR recognition.", fontsize=font_size)
            pdf_bytes = doc.tobytes()
            doc.close()
            return pdf_bytes
        else:
            # Fallback using PIL multi-page PDF creation
            images = []
            for i in range(page_count):
                img = Image.new("RGB", (width, height), color="white")
                draw = ImageDraw.Draw(img)
                draw.text((50, 72), f"{text_prefix} #{i + 1}", fill="black")
                draw.rectangle([(50, 150), (width - 50, 250)], outline="blue", width=2)
                draw.text((60, 200), f"Sample content line {i+1}", fill="black")
                images.append(img)
            
            buf = io.BytesIO()
            if images:
                images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
            return buf.getvalue()

    return _generator


@pytest.fixture
def synthetic_image_generator():
    """
    Factory fixture returning a callable to generate batches of synthetic NumPy / PIL images
    with varying aspect ratios, noise, and text.
    """
    def _generator(
        count: int = 4,
        sizes: Optional[List[Tuple[int, int]]] = None,
        text_list: Optional[List[str]] = None,
        channels: int = 3,
        as_numpy: bool = True,
    ) -> List[Union[np.ndarray, Image.Image]]:
        default_sizes = [(640, 480), (800, 600), (480, 640), (1024, 768)]
        results = []
        for i in range(count):
            w, h = (sizes[i % len(sizes)]) if sizes else default_sizes[i % len(default_sizes)]
            img = Image.new("RGB" if channels == 3 else "L", (w, h), color="white")
            draw = ImageDraw.Draw(img)
            text = text_list[i] if (text_list and i < len(text_list)) else f"Batch Item {i} text"
            draw.text((20, 20), text, fill="black")
            # Draw synthetic text box
            draw.rectangle([(20, 50), (w - 20, 100)], fill="lightgray", outline="black")
            draw.text((30, 65), f"Simulated Line Box {i}", fill="black")
            
            if as_numpy:
                arr = np.array(img)
                results.append(arr)
            else:
                results.append(img)
        return results

    return _generator


@pytest.fixture
def sample_multipage_pdf(synthetic_pdf_generator, tmp_path) -> Path:
    """Fixture creating a temporary 3-page test PDF file on disk."""
    pdf_bytes = synthetic_pdf_generator(page_count=3, text_prefix="E2E Sample Document")
    pdf_file = tmp_path / "sample_e2e_doc.pdf"
    pdf_file.write_bytes(pdf_bytes)
    return pdf_file


# ============================================================================
# 2. Mock / In-Memory Redis Client Fixture
# ============================================================================

class InMemoryRedisMock:
    """
    High-fidelity in-memory Redis mock supporting string keys, hashes, lists,
    sets, TTL expirations, BRPOP priority queues, and pub/sub primitives.
    """
    def __init__(self):
        self._kv: Dict[str, Any] = {}
        self._hashes: Dict[str, Dict[str, Any]] = {}
        self._lists: Dict[str, List[Any]] = {}
        self._sets: Dict[str, set] = {}
        self._ttls: Dict[str, float] = {}
        self._channels: Dict[str, List[Any]] = {}

    def _is_expired(self, key: str) -> bool:
        if key in self._ttls and time.time() > self._ttls[key]:
            self.delete(key)
            return True
        return False

    def ping(self) -> bool:
        return True

    def set(self, name: str, value: Any, ex: Optional[int] = None, px: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        if nx and name in self._kv:
            return False
        if xx and name not in self._kv:
            return False
        self._kv[name] = str(value) if isinstance(value, (int, float)) else value
        if ex:
            self._ttls[name] = time.time() + ex
        elif px:
            self._ttls[name] = time.time() + (px / 1000.0)
        return True

    def get(self, name: str) -> Optional[Any]:
        if self._is_expired(name):
            return None
        return self._kv.get(name)

    def delete(self, *names: str) -> int:
        count = 0
        for name in names:
            if name in self._kv:
                del self._kv[name]
                count += 1
            if name in self._hashes:
                del self._hashes[name]
                count += 1
            if name in self._lists:
                del self._lists[name]
                count += 1
            if name in self._sets:
                del self._sets[name]
                count += 1
            self._ttls.pop(name, None)
        return count

    def exists(self, *names: str) -> int:
        return sum(1 for name in names if not self._is_expired(name) and (name in self._kv or name in self._hashes or name in self._lists or name in self._sets))

    def expire(self, name: str, time_sec: int) -> bool:
        if name in self._kv or name in self._hashes or name in self._lists or name in self._sets:
            self._ttls[name] = time.time() + time_sec
            return True
        return False

    def ttl(self, name: str) -> int:
        if name in self._ttls:
            remaining = int(self._ttls[name] - time.time())
            return max(remaining, 0)
        if self.exists(name):
            return -1
        return -2

    # Hashes
    def hset(self, name: str, key: Optional[str] = None, value: Optional[Any] = None, mapping: Optional[Dict[str, Any]] = None) -> int:
        if name not in self._hashes:
            self._hashes[name] = {}
        target = self._hashes[name]
        count = 0
        if mapping:
            for k, v in mapping.items():
                target[str(k)] = str(v)
                count += 1
        if key is not None and value is not None:
            target[str(key)] = str(value)
            count += 1
        return count

    def hget(self, name: str, key: str) -> Optional[str]:
        if self._is_expired(name):
            return None
        return self._hashes.get(name, {}).get(str(key))

    def hgetall(self, name: str) -> Dict[str, str]:
        if self._is_expired(name):
            return {}
        return dict(self._hashes.get(name, {}))

    def hdel(self, name: str, *keys: str) -> int:
        if name not in self._hashes:
            return 0
        count = 0
        for k in keys:
            if str(k) in self._hashes[name]:
                del self._hashes[name][str(k)]
                count += 1
        return count

    # Lists & Queue Primitives
    def rpush(self, name: str, *values: Any) -> int:
        if name not in self._lists:
            self._lists[name] = []
        for v in values:
            self._lists[name].append(str(v) if not isinstance(v, (str, bytes)) else v)
        return len(self._lists[name])

    def lpush(self, name: str, *values: Any) -> int:
        if name not in self._lists:
            self._lists[name] = []
        for v in values:
            self._lists[name].insert(0, str(v) if not isinstance(v, (str, bytes)) else v)
        return len(self._lists[name])

    def lpop(self, name: str) -> Optional[Any]:
        if self._is_expired(name) or name not in self._lists or not self._lists[name]:
            return None
        return self._lists[name].pop(0)

    def rpop(self, name: str) -> Optional[Any]:
        if self._is_expired(name) or name not in self._lists or not self._lists[name]:
            return None
        return self._lists[name].pop()

    def llen(self, name: str) -> int:
        if self._is_expired(name):
            return 0
        return len(self._lists.get(name, []))

    def lrange(self, name: str, start: int, end: int) -> List[Any]:
        if self._is_expired(name) or name not in self._lists:
            return []
        items = self._lists[name]
        if end == -1:
            return items[start:]
        return items[start:end + 1]

    def brpop(self, keys: Union[str, List[str]], timeout: int = 0) -> Optional[Tuple[str, str]]:
        """
        Pops value from the first non-empty list in keys order (Priority Queue primitive).
        """
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            if not self._is_expired(key) and key in self._lists and len(self._lists[key]) > 0:
                val = self._lists[key].pop()
                return (key, val)
        return None

    def blpop(self, keys: Union[str, List[str]], timeout: int = 0) -> Optional[Tuple[str, str]]:
        if isinstance(keys, str):
            keys = [keys]
        for key in keys:
            if not self._is_expired(key) and key in self._lists and len(self._lists[key]) > 0:
                val = self._lists[key].pop(0)
                return (key, val)
        return None

    # PubSub & Keys
    def keys(self, pattern: str = "*") -> List[str]:
        import fnmatch
        all_keys = set(self._kv.keys()) | set(self._hashes.keys()) | set(self._lists.keys()) | set(self._sets.keys())
        active = [k for k in all_keys if not self._is_expired(k)]
        if pattern == "*":
            return active
        return fnmatch.filter(active, pattern)

    def publish(self, channel: str, message: Any) -> int:
        if channel not in self._channels:
            self._channels[channel] = []
        self._channels[channel].append(message)
        return 1

    def flushall(self):
        self._kv.clear()
        self._hashes.clear()
        self._lists.clear()
        self._sets.clear()
        self._ttls.clear()
        self._channels.clear()


@pytest.fixture
def mock_redis():
    """
    Fixture providing a fresh isolated in-memory Redis instance.
    Uses fakeredis if available, or high-fidelity InMemoryRedisMock fallback.
    """
    if HAS_FAKEREDIS:
        client = fakeredis.FakeRedis(decode_responses=True)
        yield client
        client.flushall()
    else:
        client = InMemoryRedisMock()
        yield client
        client.flushall()


@pytest.fixture
def patch_redis(mock_redis):
    """
    Autouse patch for blast_ocr.queue modules to use mock_redis.
    """
    with patch("blast_ocr.queue.client.get_redis_connection", return_value=mock_redis), \
         patch("redis.Redis.from_url", return_value=mock_redis), \
         patch("redis.from_url", return_value=mock_redis):
        yield mock_redis


# ============================================================================
# 3. FastAPI TestClient Fixture
# ============================================================================

@pytest.fixture
def test_api_client():
    """
    FastAPI TestClient fixture for blast_ocr.api.app.
    """
    if HAS_FASTAPI:
        with TestClient(fastapi_app) as client:
            yield client
    else:
        yield MagicMock()


# ============================================================================
# 4. Mock S3 / MinIO and Local Storage Backend Fixture
# ============================================================================

class MockS3StorageBackend:
    """
    In-memory S3/MinIO compatible object store for streaming uploads and tests.
    """
    def __init__(self, bucket_name: str = "blast-ocr-bucket"):
        self.bucket_name = bucket_name
        self.objects: Dict[str, bytes] = {}
        self.metadata: Dict[str, Dict[str, str]] = {}
        self.multiparts: Dict[str, Dict[int, bytes]] = {}

    def put_object(self, key: str, data: Union[bytes, str, io.BytesIO], metadata: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        if isinstance(data, str):
            raw = data.encode("utf-8")
        elif isinstance(data, io.BytesIO):
            raw = data.getvalue()
        else:
            raw = bytes(data)
        
        self.objects[key] = raw
        self.metadata[key] = metadata or {}
        return {"ETag": f'"{uuid.uuid4().hex}"', "Key": key, "Size": len(raw)}

    def get_object(self, key: str) -> Dict[str, Any]:
        if key not in self.objects:
            raise KeyError(f"Key '{key}' not found in bucket '{self.bucket_name}'")
        raw = self.objects[key]
        return {
            "Body": io.BytesIO(raw),
            "ContentLength": len(raw),
            "Metadata": self.metadata.get(key, {}),
        }

    def list_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        results = []
        for k, v in self.objects.items():
            if k.startswith(prefix):
                results.append({"Key": k, "Size": len(v), "LastModified": time.time()})
        return results

    def delete_object(self, key: str) -> bool:
        self.objects.pop(key, None)
        self.metadata.pop(key, None)
        return True

    def create_multipart_upload(self, key: str) -> str:
        upload_id = str(uuid.uuid4())
        self.multiparts[upload_id] = {}
        return upload_id

    def upload_part(self, upload_id: str, part_number: int, data: bytes) -> str:
        if upload_id not in self.multiparts:
            raise ValueError(f"Invalid upload_id: {upload_id}")
        self.multiparts[upload_id][part_number] = data
        return f"part-{part_number}-etag"

    def complete_multipart_upload(self, key: str, upload_id: str) -> Dict[str, Any]:
        if upload_id not in self.multiparts:
            raise ValueError(f"Invalid upload_id: {upload_id}")
        parts = self.multiparts.pop(upload_id)
        sorted_parts = [parts[k] for k in sorted(parts.keys())]
        full_data = b"".join(sorted_parts)
        return self.put_object(key, full_data)

    def put(self, key: str, local_path: Union[str, Path]) -> str:
        data = Path(local_path).read_bytes()
        self.put_object(key, data)
        return f"s3://{self.bucket_name}/{key}"

    def get(self, key: str, dest_path: Union[str, Path]) -> str:
        res = self.get_object(key)
        Path(dest_path).write_bytes(res["Body"].getvalue())
        return str(dest_path)

    def exists(self, key: str) -> bool:
        return key in self.objects

    def delete(self, key: str) -> None:
        self.delete_object(key)

    def put_bytes(self, key: str, data: bytes) -> str:
        self.put_object(key, data)
        return f"s3://{self.bucket_name}/{key}"

    def put_stream(self, key: str, stream: Any, content_length: Optional[int] = None) -> str:
        data = stream.read()
        self.put_object(key, data)
        return f"s3://{self.bucket_name}/{key}"

    def get_stream(self, key: str) -> io.BytesIO:
        res = self.get_object(key)
        return res["Body"]

    def put_multipart(self, key: str, local_path: Union[str, Path], chunk_size: int = 8 * 1024 * 1024) -> str:
        return self.put(key, local_path)

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"https://s3.amazonaws.com/{self.bucket_name}/{key}?signature=mock"


@pytest.fixture
def mock_s3_storage():
    """Fixture providing a mock S3/MinIO storage backend."""
    return MockS3StorageBackend()


# ============================================================================
# 5. Mock ONNX Runtime Session & Tensor Helpers
# ============================================================================

class MockONNXInferenceSession:
    """
    Configurable Mock ONNX Runtime InferenceSession supporting DBNet detection
    and CTC recognition tensor contracts.
    """
    def __init__(self, model_path: str = "mock_model.onnx", providers: Optional[List[str]] = None, **kwargs):
        self.model_path = model_path
        self.providers = providers or ["CPUExecutionProvider"]
        self.active_provider = self.providers[0] if self.providers else "CPUExecutionProvider"
        self._inputs = [MagicMock(name="x", shape=[-1, 3, 48, -1])]
        self._outputs = [MagicMock(name="output", shape=[-1, -1, 6625])]

    def get_providers(self) -> List[str]:
        return self.providers

    def get_inputs(self):
        return self._inputs

    def get_outputs(self):
        return self._outputs

    def run(self, output_names: Optional[List[str]], input_feed: Dict[str, np.ndarray], run_options=None) -> List[np.ndarray]:
        """
        Dynamically handles detection or recognition feeds and returns realistic tensors.
        """
        input_tensor = next(iter(input_feed.values()))
        batch_size = input_tensor.shape[0]

        # Check if recognition tensor (height == 48 or 32)
        if len(input_tensor.shape) == 4 and input_tensor.shape[2] in (32, 48):
            seq_len = max(input_tensor.shape[3] // 4, 10)
            vocab_size = 6625
            # Synthetic CTC logits: batch_size x seq_len x vocab_size
            logits = np.random.randn(batch_size, seq_len, vocab_size).astype(np.float32)
            # Bias specific indices to represent deterministic characters
            logits[:, 1:4, 10] = 5.0  # token 10
            logits[:, 5:7, 20] = 5.0  # token 20
            return [logits]
        else:
            # DBNet detection tensor: batch_size x 1 x H x W probability map
            h = input_tensor.shape[2] if len(input_tensor.shape) == 4 else 640
            w = input_tensor.shape[3] if len(input_tensor.shape) == 4 else 640
            prob_map = np.zeros((batch_size, 1, h, w), dtype=np.float32)
            # Create a high probability text box region
            prob_map[:, 0, 50:120, 50:300] = 0.95
            return [prob_map]


@pytest.fixture
def mock_onnx_session_factory():
    """Factory fixture returning a MockONNXInferenceSession."""
    def _factory(model_path: str = "model.onnx", providers: Optional[List[str]] = None, **kwargs):
        return MockONNXInferenceSession(model_path=model_path, providers=providers, **kwargs)
    return _factory
