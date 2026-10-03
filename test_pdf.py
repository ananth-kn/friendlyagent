from pdf_to_images import pdf_to_images

pdf_path = "downloads/Computer_Networks_Assignment.pdf"

images = pdf_to_images(pdf_path)

print("\nGenerated images:")

for image in images:
    print(image)