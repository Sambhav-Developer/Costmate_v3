import zipfile
import xml.etree.ElementTree as ET

def get_docx_text(path):
    try:
        doc = zipfile.ZipFile(path)
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
        return f"Error: {e}"

if __name__ == '__main__':
    doc_path = r"c:\Users\Hp\Desktop\Costmate_v3\Assets\Yale\YALE NEW HAVEN HEALTH DAY 4.docx"
    text = get_docx_text(doc_path)
    print("EXTRACTED TEXT LENGTH:", len(text))
    # Write first 5000 characters to a txt file to inspect
    with open("extracted_docx_sample.txt", "w", encoding="utf-8") as f:
        f.write(text)
    print("Done")
