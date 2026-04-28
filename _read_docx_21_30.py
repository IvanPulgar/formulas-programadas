"""Lee el texto completo del .docx y lo imprime para extraer EX21-30."""
from pathlib import Path
from docx import Document

docx = next(Path(".").glob("*.docx"))
print(f"FILE: {docx.name}\n{'='*60}")
doc = Document(str(docx))
for i, para in enumerate(doc.paragraphs):
    txt = para.text.strip()
    if txt:
        print(f"[{i:4d}] {txt}")
