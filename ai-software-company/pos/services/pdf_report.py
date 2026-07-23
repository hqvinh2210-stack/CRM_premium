"""Minimal PDF generator for sales reports (no external PDF libs)."""

from __future__ import annotations


def _escape_pdf_text(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def text_report_to_pdf(lines: list[str], *, title: str = "CRM Premium Report") -> bytes:
    """
    Build a simple multi-line PDF (Helvetica) from plain text lines.
    Suitable for EOD / export (P4-M6).
    """
    y_start = 780
    line_height = 14
    body_lines = lines[:50]
    content_parts = [
        "BT",
        "/F1 14 Tf",
        f"50 {y_start} Td",
        f"({_escape_pdf_text(title)}) Tj",
        "0 -20 Td",
        "/F1 10 Tf",
    ]
    for i, line in enumerate(body_lines):
        if i > 0:
            content_parts.append(f"0 -{line_height} Td")
        content_parts.append(f"({_escape_pdf_text(line[:110])}) Tj")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", errors="replace")

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = [0]

    def write_obj(n: int, body: bytes) -> None:
        while len(offs) <= n:
            offs.append(0)
        offs[n] = len(out)
        out.extend(f"{n} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")

    write_obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    write_obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    write_obj(
        3,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    )
    write_obj(4, b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    write_obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offs)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for i in range(1, len(offs)):
        out.extend(f"{offs[i]:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(offs)} /Root 1 0 R /Info << /Title ({_escape_pdf_text(title)}) >> >>\n".encode()
    )
    out.extend(b"startxref\n")
    out.extend(f"{xref_pos}\n".encode())
    out.extend(b"%%EOF\n")
    return bytes(out)
