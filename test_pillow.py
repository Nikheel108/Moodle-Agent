from PIL import Image, ImageDraw, ImageFont

text = """$ python main.py
Hello World!
Array: [1, 2, 3, 4, 5]
Sum: 15
Time taken: 0.02ms"""

def create_terminal_screenshot(text, filepath):
    try:
        font = ImageFont.truetype("consola.ttf", 18)
    except IOError:
        font = ImageFont.load_default()
    
    lines = text.split('\n')
    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    max_width = 0
    total_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_width = max(max_width, bbox[2] - bbox[0])
        total_height += (bbox[3] - bbox[1]) + 6
        
    width = max(600, max_width + 40)
    height = max(300, total_height + 70)
    
    img = Image.new('RGB', (width, height), color=(12, 12, 12))
    draw = ImageDraw.Draw(img)
    
    # Draw terminal top bar
    draw.rectangle([0, 0, width, 35], fill=(35, 35, 35))
    draw.ellipse([12, 10, 27, 25], fill=(255, 95, 86))
    draw.ellipse([37, 10, 52, 25], fill=(255, 189, 46))
    draw.ellipse([62, 10, 77, 25], fill=(39, 201, 63))
    draw.text((width // 2 - 40, 8), "cmd.exe", font=font, fill=(180, 180, 180))
    
    y_text = 45
    for line in lines:
        draw.text((20, y_text), line, font=font, fill=(204, 204, 204))
        bbox = draw.textbbox((0, 0), line, font=font)
        y_text += (bbox[3] - bbox[1]) + 6

    img.save(filepath)

create_terminal_screenshot(text, "test_snap.png")
print("Done")
