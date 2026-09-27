import base64
from pathlib import Path
from xhtml2pdf import pisa
from PIL import Image, ImageDraw, ImageFont

def create_dummy():
    img = Image.new('RGB', (600, 300), color=(12, 12, 12))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 600, 35], fill=(35, 35, 35))
    draw.text((20, 50), "Hello Base64", fill=(204, 204, 204))
    img.save("dummy.png")
    
    with open("dummy.png", "rb") as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
        
    html = f"""
    <html>
    <body>
    <h1>Test Image</h1>
    <img src="data:image/png;base64,{b64}" width="600" />
    </body>
    </html>
    """
    
    with open("test.pdf", "wb") as f:
        pisa.CreatePDF(html, dest=f)

create_dummy()
print("Done")
