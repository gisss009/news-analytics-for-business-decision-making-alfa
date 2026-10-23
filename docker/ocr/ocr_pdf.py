"""Постраничный текст PDF (внутри контейнера OCR): текстовый слой, а если его нет — Tesseract rus+eng.

Вход: /data/*.pdf (папка data/analytics хоста). Выход: /data/.ocr/<имя файла>.json
{"file", "sha256", "engine", "dpi", "pages": [{"page", "text", "method"}]}. Файл с тем же sha256 не пересчитывается.
Запуск снаружи: python scripts/ocr.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pypdfium2 as pdfium

DATA = Path("/data")
OUT = DATA / ".ocr"
DPI = 200
MIN_TEXT_LAYER = 50  # меньше символов на странице — считаем, что текстового слоя нет


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tesseract(image_path: Path) -> str:
    r = subprocess.run(["tesseract", str(image_path), "stdout", "-l", "rus+eng", "--psm", "3"],
                       capture_output=True, text=True, check=True)
    return r.stdout


def process(pdf: Path, force: bool) -> dict:
    digest = sha256(pdf)
    out = OUT / f"{pdf.name}.json"
    if out.exists() and not force:
        cached = json.loads(out.read_text(encoding="utf-8"))
        if cached.get("sha256") == digest:
            return {"file": pdf.name, "pages": len(cached["pages"]), "cached": True}
    doc = pdfium.PdfDocument(str(pdf))
    pages = []
    t0 = time.time()
    with tempfile.TemporaryDirectory() as tmp:
        for i in range(len(doc)):
            page = doc[i]
            layer = page.get_textpage().get_text_bounded() or ""
            if len(layer.strip()) >= MIN_TEXT_LAYER:
                pages.append({"page": i + 1, "text": layer, "method": "text_layer"})
                continue
            img = Path(tmp) / f"p{i + 1}.png"
            page.render(scale=DPI / 72).to_pil().save(img)
            pages.append({"page": i + 1, "text": tesseract(img), "method": "ocr"})
    OUT.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"file": pdf.name, "sha256": digest, "engine": "tesseract rus+eng", "dpi": DPI,
                               "pages": pages}, ensure_ascii=False), encoding="utf-8")
    return {"file": pdf.name, "pages": len(pages), "cached": False, "seconds": round(time.time() - t0, 1)}


def main() -> int:
    force = "--force" in sys.argv
    pdfs = sorted(DATA.glob("*.pdf"))
    if not pdfs:
        print("нет PDF в папке data/analytics", flush=True)
        return 1
    for pdf in pdfs:
        print(json.dumps(process(pdf, force), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
