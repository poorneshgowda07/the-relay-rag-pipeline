from pathlib import Path
import json

md_text = Path("the-relay/writeup.md").read_text(encoding="utf-8")
json_md = json.dumps(md_text)

html_template = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>The Relay - Assignment Submission</title>
<style>
  @page {
    size: letter;
    margin: 16mm 14mm;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1f2937;
    line-height: 1.45;
    font-size: 10pt;
    max-width: 900px;
    margin: 0 auto;
    padding: 24px;
  }
  h1 { font-size: 18pt; border-bottom: 2px solid #2563eb; padding-bottom: 6px; margin-top: 0; color: #1e3a8a; }
  h2, h3 { font-size: 12pt; color: #1e40af; margin-top: 14px; margin-bottom: 6px; border-bottom: 1px solid #e5e7eb; padding-bottom: 3px; }
  h4 { font-size: 10.5pt; color: #374151; margin-top: 8px; margin-bottom: 4px; }
  p { margin-top: 4px; margin-bottom: 6px; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0 12px 0;
    font-size: 9pt;
  }
  th, td {
    border: 1px solid #d1d5db;
    padding: 4px 6px;
    text-align: left;
  }
  th {
    background-color: #f3f4f6;
    font-weight: 600;
    color: #111827;
  }
  tr:nth-child(even) { background-color: #f9fafb; }
  blockquote {
    border-left: 3px solid #3b82f6;
    background-color: #eff6ff;
    margin: 6px 0;
    padding: 6px 12px;
    font-size: 9.5pt;
    color: #1e3a8a;
  }
  code {
    background-color: #f3f4f6;
    padding: 2px 4px;
    border-radius: 4px;
    font-size: 8.5pt;
    font-family: Consolas, monospace;
  }
  ul, ol { margin-top: 4px; margin-bottom: 6px; padding-left: 18px; }
  li { margin-bottom: 2px; }
</style>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
<div id="content"></div>
<script>
  const rawMarkdown = __MD_JSON__;
  document.getElementById('content').innerHTML = marked.parse(rawMarkdown);
</script>
</body>
</html>
"""

final_html = html_template.replace("__MD_JSON__", json_md)
Path("the-relay/writeup.html").write_text(final_html, encoding="utf-8")
Path("writeup.html").write_text(final_html, encoding="utf-8")
print("Generated writeup.html successfully!")
