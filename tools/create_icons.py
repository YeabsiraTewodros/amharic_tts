from PIL import Image, ImageDraw, ImageFont
import os
BASE = os.path.join(os.path.dirname(__file__), '..', 'static')
os.makedirs(BASE, exist_ok=True)

def make_icon(size, filename, bg='#2b7a78', fg='#ffffff'):
    img = Image.new('RGBA', (size, size), bg)
    draw = ImageDraw.Draw(img)
    try:
        # Try to use a default system font
        font = ImageFont.truetype('arial.ttf', size // 2)
    except Exception:
        font = ImageFont.load_default()
    text = 'አ'
    try:
        w, h = draw.textsize(text, font=font)
    except Exception:
        bbox = font.getbbox(text)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size-w)/2, (size-h)/2), text, font=font, fill=fg)
    path = os.path.join(BASE, filename)
    img.save(path)
    print('Wrote', path)

if __name__ == '__main__':
    make_icon(192, 'icon-192.png')
    make_icon(512, 'icon-512.png')
