# 🤝 Contributing to B.L.A.S.T.

Thank you for your interest in improving the B.L.A.S.T. OCR Engine!

## 🛠️ Development Setup

1. **Fork & Clone**
   ```bash
   git clone https://github.com/your-username/blast-ocr.git
   ```
2. **Install Dev Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install pytest pylint black
   ```

## 🧪 Testing

We use `pytest` for unit and integration testing.

- **Run all tests**:
  ```bash
  python -m pytest tests/
  ```
- **Run specific test**:
  ```bash
  python -m pytest tests/test_extractor.py
  ```

### Writing Tests
- Place new tests in `tests/`.
- Use the `temp_workspace` fixture for file I/O tests.
- Mock external calls (like heavy OCR models) where appropriate, but we prefer integration tests on small sample images.

## 📐 Coding Standards

- **Style**: Follow PEP 8.
- **Type Hinting**: Use Python type hints (`List`, `Dict`, `Optional`) for all function signatures.
- **Docstrings**: All modules, classes, and public functions must have docstrings.
- **Architecture**: Respect the 3-Layer separation. Do not put business logic in the UI layer.

## 🚀 Pull Request Process

1. Create a feature branch (`git checkout -b feature/amazing-feature`).
2. Commit your changes.
3. Push to the branch.
4. Open a Pull Request.
5. Ensure all tests pass.
