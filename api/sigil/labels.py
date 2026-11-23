"""QR codes and printable label sheets."""

from __future__ import annotations

import io
from urllib.parse import urlparse

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def verify_url(base_url: str, public_code: str, serial: str) -> str:
    return f"{base_url.rstrip('/')}/v/{public_code}/{serial}"


def qr_png(url: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def labels_pdf(
    *,
    base_url: str,
    public_code: str,
    product_name: str,
    batch_number: str,
    serials: list[str],
    columns: int = 3,
    rows: int = 7,
) -> bytes:
    """A simple printable sheet. Each label carries the QR, the plain domain and serial."""
    host = urlparse(base_url).netloc or base_url
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 10 * mm
    cell_w = (width - 2 * margin) / columns
    cell_h = (height - 2 * margin) / rows
    qr_size = min(cell_w, cell_h) - 18 * mm

    for index, serial in enumerate(serials):
        position = index % (columns * rows)
        if position == 0 and index > 0:
            page.showPage()
        column = position % columns
        row = position // columns
        x = margin + column * cell_w
        y = height - margin - (row + 1) * cell_h

        page.setStrokeColorRGB(0.8, 0.8, 0.8)
        page.rect(x + 1 * mm, y + 1 * mm, cell_w - 2 * mm, cell_h - 2 * mm)

        png = qr_png(verify_url(base_url, public_code, serial))
        page.drawImage(
            ImageReader(io.BytesIO(png)),
            x + 4 * mm,
            y + (cell_h - qr_size) / 2,
            qr_size,
            qr_size,
        )

        text_x = x + qr_size + 7 * mm
        text_y = y + cell_h - 8 * mm
        page.setFont("Helvetica-Bold", 7)
        page.drawString(text_x, text_y, product_name[:34])
        page.setFont("Helvetica", 6)
        page.drawString(text_x, text_y - 4 * mm, f"Batch {batch_number}"[:34])
        page.setFont("Helvetica-Bold", 6)
        page.drawString(text_x, text_y - 8 * mm, host[:34])
        page.setFont("Courier", 5.5)
        page.drawString(text_x, text_y - 12 * mm, serial)

    page.showPage()
    page.save()
    return buffer.getvalue()
