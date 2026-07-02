from __future__ import annotations

from html import escape

from app.models.idm import Block, DocumentModel, Run


def idm_to_html(document: DocumentModel) -> str:
    body = "\n".join(_block_to_html(block) for page in document.pages for block in page.blocks)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(document.source_file_name)} reconstructed</title>
<style>
body {{ font-family: Arial, sans-serif; line-height: 1.45; color: #111; }}
.clause-number {{ font-weight: 700; margin-right: 0.35rem; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
td, th {{ border: 1px solid #000; padding: 0.35rem 0.5rem; vertical-align: top; }}
.page-break {{ page-break-after: always; border-top: 1px dashed #999; margin: 1.5rem 0; }}
@media print {{ .page-break {{ page-break-after: always; }} }}
</style>
</head>
<body>
{body}
</body>
</html>"""


def _block_to_html(block: Block) -> str:
    if block.type == "heading":
        level = int(block.attrs.get("level", 1))
        return f"<h{level}>{_runs(block.runs or [])}</h{level}>"
    if block.type == "paragraph":
        alignment = escape(str(block.attrs.get("alignment", "left")))
        indent = int(block.attrs.get("indentLevel", 0)) * 20
        return f'<p style="text-align:{alignment}; margin-left:{indent}px">{_runs(block.runs or [])}</p>'
    if block.type == "clauseNumber":
        return f'<p><span class="clause-number"><strong>{_runs(block.runs or [])}</strong></span></p>'
    if block.type == "signatureLine":
        return f"<p>{_runs(block.runs or [])}</p>"
    if block.type == "pageBreak":
        return '<div class="page-break"></div>'
    if block.type == "list":
        tag = "ul" if block.attrs.get("listType") == "bullet" else "ol"
        start = f' start="{int(block.attrs.get("startNumber", 1))}"' if tag == "ol" else ""
        return f"<{tag}{start}>{''.join(_block_to_html(child) for child in block.children or [])}</{tag}>"
    if block.type == "listItem":
        return f"<li>{_runs(block.runs or [])}</li>"
    if block.type == "table":
        return f"<table>{''.join(_block_to_html(child) for child in block.children or [])}</table>"
    if block.type == "tableRow":
        return f"<tr>{''.join(_block_to_html(child) for child in block.children or [])}</tr>"
    if block.type == "tableCell":
        row_span = int(block.attrs.get("rowSpan", 1))
        col_span = int(block.attrs.get("colSpan", 1))
        return f'<td rowspan="{row_span}" colspan="{col_span}">{_runs(block.runs or [])}</td>'
    return ""


def _runs(runs: list[Run]) -> str:
    return "".join(_run(run) for run in runs)


def _run(run: Run) -> str:
    text = escape(run.text).replace("\n", "<br>")
    style = []
    if run.marks.color:
        style.append(f"color:{escape(run.marks.color)}")
    if run.marks.highlight:
        style.append(f"background-color:{escape(run.marks.highlight)}")
    if run.marks.bold:
        text = f"<strong>{text}</strong>"
    if run.marks.italic:
        text = f"<em>{text}</em>"
    if run.marks.underline:
        text = f"<u>{text}</u>"
    if style:
        text = f'<span style="{";".join(style)}">{text}</span>'
    return text
