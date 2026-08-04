import pathlib

path = pathlib.Path(r'c:\Users\Kevin\OneDrive\Documents\GitHub\semantic-query-agent\app.py')
text = path.read_text(encoding='utf-8')

old = "        num_tables = str(schema.upper().count(\"CREATE TABLE\")) if schema else \"0\""
new = "        num_tables = str(len(set(re.findall(r'\\b(?:FROM|JOIN)\\s+\"?(\\w+)\"?', sql, re.IGNORECASE)))) if sql else \"0\""

if old in text:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding='utf-8')
    print("Fixed.")
else:
    print("Pattern not found. Showing line with num_tables:")
    for i, line in enumerate(text.splitlines(), 1):
        if 'num_tables' in line:
            print(f"  line {i}: {repr(line)}")
