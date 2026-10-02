"""Generates a dummy PDF lab report for testing /analyze_report.

Writes the PDF structure directly rather than pulling in a PDF library: the
file only needs a text layer that pypdf can read, and a fixture should not add
a dependency to the service it tests.

Usage:  python make_dummy_report.py [output.pdf]
"""

import sys

PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4 in points

# Deliberately mixed so every classifier path is exercised:
#   - numeric in range, numeric high/low, numeric critically high/low
#   - qualitative normal ("Negative") and qualitative abnormal ("3+")
#   - one row with no reference range at all
LINES = [
    ("title", "RIVERSIDE CLINICAL LABORATORY"),
    ("sub", "Comprehensive Metabolic & Haematology Panel"),
    ("gap", ""),
    ("body", "Patient Name:   Jane A. Doe"),
    ("body", "Date of Birth:  1988-03-14"),
    ("body", "Sex:            Female"),
    ("body", "Report Date:    2026-09-28"),
    ("body", "Accession No:   RCL-2026-884120"),
    ("gap", ""),
    ("head", "Test Name                     Result      Unit        Reference Range"),
    ("rule", "-" * 78),
    ("body", "Haemoglobin                   14.2        g/dL        12.0 - 16.0"),
    ("body", "Leukocytes                    34.5        10^3/uL     5.0 - 10.6"),
    ("body", "Platelets                     210         10^3/uL     150 - 400"),
    ("body", "Potassium                     2.6         mmol/L      3.5 - 5.1"),
    ("body", "Sodium                        139         mmol/L      136 - 145"),
    ("body", "Creatinine                    0.9         mg/dL       0.6 - 1.2"),
    ("body", "Glucose (Fasting)             118         mg/dL       70 - 99"),
    ("body", "HbA1c                         6.4         %           4.0 - 6.0"),
    ("body", "Total Cholesterol             243         mg/dL       0 - 200"),
    ("body", "ALT (SGPT)                    67          U/L         7 - 56"),
    ("body", "TSH                           2.1         mIU/L       0.4 - 4.0"),
    ("body", "Vitamin D (25-OH)             18          ng/mL       30 - 100"),
    ("body", "Urine Protein                 Negative    -           Negative"),
    ("body", "Urine Blood                   3+          -           Negative"),
    ("body", "C-Reactive Protein            8.9         mg/L"),
    ("gap", ""),
    ("note", "Comments: Marked leukocytosis and hypokalaemia noted. Clinical"),
    ("note", "correlation and urgent review recommended."),
    ("gap", ""),
    ("note", "This is a SYNTHETIC report generated for software testing."),
    ("note", "It does not describe a real person and must not be used clinically."),
]

STYLES = {
    "title": (16, 26),
    "sub": (11, 20),
    "head": (10, 16),
    "rule": (10, 12),
    "body": (10, 14),
    "note": (9, 13),
    "gap": (10, 10),
}


def escape(text):
    """Backslash, parens and non-ASCII would otherwise corrupt the content stream."""
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in out)


def build_content():
    parts = ["BT"]
    y = PAGE_HEIGHT - 60
    first = True
    for kind, text in LINES:
        size, leading = STYLES[kind]
        parts.append(f"/F1 {size} Tf")
        if first:
            parts.append(f"50 {y} Td")
            first = False
        else:
            parts.append(f"0 -{leading} Td")
        if text:
            parts.append(f"({escape(text)}) Tj")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1")


def build_pdf():
    content = build_content()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("latin-1"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    return bytes(out)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "dummy_lab_report.pdf"
    with open(target, "wb") as fh:
        fh.write(build_pdf())
    print(f"wrote {target}")
