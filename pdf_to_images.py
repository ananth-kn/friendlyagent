import os
import fitz


def pdf_to_images(pdf_path, output_dir="pdf_pages"):
    print("converting pdf to image")
    os.makedirs(output_dir, exist_ok=True)

    pdf = fitz.open(pdf_path)

    image_paths = []

    for page_number, page in enumerate(pdf, start=1):

        # 150 DPI is enough for LLM vision while keeping files reasonable
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(150 / 72, 150 / 72),
            alpha=False
        )

        image_path = os.path.join(
            output_dir,
            f"page_{page_number}.png"
        )

        pixmap.save(image_path)

        image_paths.append(image_path)

        print(f"Rendered page {page_number}: {image_path}")

    pdf.close()

    return image_paths