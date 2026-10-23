# OCR материалов аналитики банка без установки Tesseract на машину.
# Tesseract (Apache-2.0) с языками rus+eng, рендер страниц PDF — pypdfium2 (Apache-2.0 / BSD-3), Pillow (MIT-CMU).
# PyMuPDF не используется: лицензия AGPL-3.0.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pypdfium2==4.30.0 pillow==11.0.0

COPY ocr_pdf.py /app/ocr_pdf.py
WORKDIR /data
ENTRYPOINT ["python", "/app/ocr_pdf.py"]
