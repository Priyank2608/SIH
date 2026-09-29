import base64
import io

import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def signature_png_data():
    image = Image.new("RGBA", (1000, 280), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line([(90, 185), (170, 70), (230, 190), (320, 115), (410, 160), (525, 95), (610, 170), (740, 80), (875, 145)],
              fill=(16, 43, 70, 255), width=9, joint="curve")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")
