
from app.ocr.pipeline import process_pdf
import re
from app.ocr.field_engine import SpatialFieldEngine

def test():
    with open(r'D:\HarshalProjects\Projects\01 - ROBO1040 - All Documents\01 - ROBO - Sample PDF Document - 10 Set\01 - W2 Form - Sample Document (10 Set)\03 - Document - Form W-2.pdf', 'rb') as f:
        file_bytes = f.read()
    
    import fitz
    doc = fitz.open(stream=file_bytes, filetype='pdf')
    text = doc[0].get_text('text')
    eng = SpatialFieldEngine(text=text)
    no_space = re.sub(r'\s+', '', eng.text)
    print(no_space)

test()

