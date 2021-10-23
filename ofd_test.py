from core.document import OFDFile
import os
import img2pdf

folder = "ofds"
for path in os.listdir(folder):
    if not path.endswith(".ofd"):
        continue
    file_path = os.path.join(folder, path)
    print(f"> Reading from OFD: {file_path}")
    doc = OFDFile(file_path)
    png_paths = [p.as_posix() for p in doc.draw_document(destination=folder)]
    print(f"> Converted PNG(s):")
    print("\n".join(png_paths))
    pdf_path = os.path.join(folder, path.replace(".ofd", ".pdf"))
    print(f"> Writing to PDF: {pdf_path}")
    with open(pdf_path, 'wb') as pdf:
        pdf.write(img2pdf.convert(png_paths))
