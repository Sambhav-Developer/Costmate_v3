
import sys

path = r" e:\sambhav projects\CosmateV3\Costmate_v3\Frontend\src\components\editor\ScheduleTables.tsx\
with open(path, \r\, encoding=\utf-8\, errors=\ignore\) as f:
 text = f.read()

# Replace any corrupted characters with simple dashes
import re
text = re.sub(r\[^\x00-\x7F]+\, \-\, text)

with open(path, \w\, encoding=\utf-8\, newline=\\) as f:
 f.write(text)
print(\Fixed encoding\)

