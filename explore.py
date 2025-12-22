import pdfplumber
from PIL import ImageDraw

with pdfplumber.open("INTERNET-MORVAN.pdf") as pdf:
    page = pdf.pages[1]
    im = page.to_image(resolution=150)
    draw = ImageDraw.Draw(im.original)

    for w in page.extract_words():
        draw.rectangle([w["x0"], w["top"], w["x1"], w["bottom"]], outline="red")

    im.show()

