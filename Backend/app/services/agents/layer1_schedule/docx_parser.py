import zipfile
import xml.etree.ElementTree as ET
from app.core.logging import logger

def extract_docx_text(file_path: str) -> str:
    """Extracts raw text from a .docx file using standard zipfile and xml libraries."""
    if not file_path:
        return ""
    try:
        doc = zipfile.ZipFile(file_path)
        xml_content = doc.read('word/document.xml')
        root = ET.fromstring(xml_content)
        
        # Namespaces
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        texts = []
        for paragraph in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
            p_text = "".join(node.text for node in paragraph.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text)
            if p_text:
                texts.append(p_text)
        return "\n".join(texts)
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX {file_path}: {e}")
        return ""
