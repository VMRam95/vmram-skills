#!/usr/bin/env python3
"""
Doc Generator - Convert Markdown to styled HTML documents
Usage: python3 generate.py --input file.md --template aws --output output.html
"""

import argparse
import re
import os
from pathlib import Path

SKILL_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"


def load_template(template_name: str) -> str:
    """Load HTML template by name."""
    template_path = TEMPLATES_DIR / f"{template_name}.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template '{template_name}' not found at {template_path}")
    return template_path.read_text(encoding="utf-8")


def parse_markdown(md: str) -> dict:
    """Extract title and convert markdown to HTML."""
    lines = md.strip().split('\n')

    # Extract title from first h1
    title = "Documento"
    for line in lines:
        if line.startswith('# '):
            title = line[2:].strip()
            break

    # Convert markdown to HTML
    html_content = convert_md_to_html(md)

    return {
        "title": title,
        "content": html_content
    }


def convert_md_to_html(md: str) -> str:
    """Convert markdown to HTML with proper styling classes."""
    html = md

    # Code blocks (```...```) - do this first to protect code content
    code_blocks = []
    def save_code_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        # Escape HTML in code
        code = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        code_blocks.append(f'<pre><code class="language-{lang}">{code}</code></pre>')
        return f'__CODE_BLOCK_{len(code_blocks)-1}__'

    html = re.sub(r'```(\w*)\n(.*?)```', save_code_block, html, flags=re.DOTALL)

    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Headers
    html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

    # Alerts/callouts (> **AVISO:** or > **WARNING:** etc)
    def convert_alert(match):
        content = match.group(1).strip()
        alert_type = 'info'
        if '⚠️' in content or 'AVISO' in content.upper() or 'WARNING' in content.upper():
            alert_type = 'warning'
        elif 'ERROR' in content.upper() or 'DANGER' in content.upper() or 'PELIGRO' in content.upper():
            alert_type = 'danger'
        elif 'NOTA' in content.upper() or 'NOTE' in content.upper() or 'INFO' in content.upper():
            alert_type = 'info'
        # Remove the > prefix from each line
        content = re.sub(r'^>\s*', '', content, flags=re.MULTILINE)
        return f'<div class="alert alert-{alert_type}">{content}</div>'

    html = re.sub(r'((?:^>.*\n?)+)', convert_alert, html, flags=re.MULTILINE)

    # Tables
    def convert_table(match):
        table_text = match.group(0)
        lines = [l.strip() for l in table_text.strip().split('\n') if l.strip()]

        if len(lines) < 2:
            return table_text

        # Parse header
        header_cells = [c.strip() for c in lines[0].split('|') if c.strip()]

        # Skip separator line
        # Parse body rows
        body_rows = []
        for line in lines[2:]:
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                body_rows.append(cells)

        # Build HTML table
        html_table = '<table>\n<thead>\n<tr>\n'
        for cell in header_cells:
            html_table += f'<th>{cell}</th>\n'
        html_table += '</tr>\n</thead>\n<tbody>\n'

        for row in body_rows:
            html_table += '<tr>\n'
            for cell in row:
                html_table += f'<td>{cell}</td>\n'
            html_table += '</tr>\n'

        html_table += '</tbody>\n</table>'
        return html_table

    # Match tables (lines starting with |)
    html = re.sub(r'((?:^\|.*\|$\n?)+)', convert_table, html, flags=re.MULTILINE)

    # Horizontal rules
    html = re.sub(r'^---+$', r'<hr>', html, flags=re.MULTILINE)

    # Unordered lists
    def convert_ul(match):
        items = match.group(0)
        list_items = re.findall(r'^[\-\*]\s+(.+)$', items, re.MULTILINE)
        if not list_items:
            return items
        html_list = '<ul>\n'
        for item in list_items:
            html_list += f'<li>{item}</li>\n'
        html_list += '</ul>'
        return html_list

    html = re.sub(r'((?:^[\-\*]\s+.+$\n?)+)', convert_ul, html, flags=re.MULTILINE)

    # Ordered lists
    def convert_ol(match):
        items = match.group(0)
        list_items = re.findall(r'^\d+\.\s+(.+)$', items, re.MULTILINE)
        if not list_items:
            return items
        html_list = '<ol>\n'
        for item in list_items:
            html_list += f'<li>{item}</li>\n'
        html_list += '</ol>'
        return html_list

    html = re.sub(r'((?:^\d+\.\s+.+$\n?)+)', convert_ol, html, flags=re.MULTILINE)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Paragraphs (wrap remaining text blocks)
    lines = html.split('\n')
    result = []
    in_paragraph = False

    for line in lines:
        stripped = line.strip()

        # Skip if it's already an HTML tag or empty
        if not stripped:
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            result.append('')
            continue

        if stripped.startswith('<') or stripped.startswith('__CODE_BLOCK_'):
            if in_paragraph:
                result.append('</p>')
                in_paragraph = False
            result.append(line)
            continue

        # Regular text - wrap in paragraph
        if not in_paragraph:
            result.append('<p>' + line)
            in_paragraph = True
        else:
            result.append(line)

    if in_paragraph:
        result.append('</p>')

    html = '\n'.join(result)

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        html = html.replace(f'__CODE_BLOCK_{i}__', block)

    return html


def generate_document(input_path: str, template_name: str, output_path: str, title_override: str = None):
    """Generate styled HTML document from markdown."""
    # Read input markdown
    md_content = Path(input_path).read_text(encoding="utf-8")

    # Parse markdown
    parsed = parse_markdown(md_content)

    # Load template
    template = load_template(template_name)

    # Replace placeholders
    title = title_override or parsed["title"]
    html = template.replace("{{TITLE}}", title)
    html = html.replace("{{CONTENT}}", parsed["content"])

    # Write output
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")

    print(f"Generated: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to styled HTML")
    parser.add_argument("--input", "-i", required=True, help="Input markdown file")
    parser.add_argument("--template", "-t", default="corporate",
                        choices=["aws", "corporate", "minimal", "tech", "presupuesto"],
                        help="Template style")
    parser.add_argument("--output", "-o", required=True, help="Output HTML file")
    parser.add_argument("--title", help="Override document title")

    args = parser.parse_args()
    generate_document(args.input, args.template, args.output, args.title)


if __name__ == "__main__":
    main()
