---
name: images-to-pdf
description: Convert multiple images (JPG, PNG, etc.) to a single PDF document. Use when a user requests to combine, merge, or convert image files into PDF format. Handles ordering, numbering, and maintains image quality.
---

# Images to PDF Converter

Convert multiple images into a single PDF document while preserving quality and respecting the user's specified order.

## Prerequisites

This skill requires the `img2pdf` Python package:

```bash
python3 -m pip install --user --break-system-packages img2pdf
```

The command-line tool will be available at `~/.local/bin/img2pdf` or directly as `img2pdf` if pip bin is in PATH.

## Basic Usage

### Simple Conversion

Convert images in the order they are listed:

```bash
img2pdf image1.jpg image2.jpg image3.jpg -o output.pdf
```

### From Variables

When working with dynamic file paths:

```bash
img2pdf \
  /path/to/first.jpg \
  /path/to/second.jpg \
  /path/to/third.jpg \
  -o /output/path/document.pdf
```

## Critical: Handling Image Order

**Default behavior:** Use the order in which images were received (arrival order).

### Standard Workflow

When a user sends multiple images:

1. **Use arrival order by default** - First image received = page 1, second = page 2, etc.
2. Process the images immediately using that order
3. No need to ask for confirmation unless the user explicitly indicates a different order is needed

### When User Specifies Different Order

Only deviate from arrival order if the user explicitly:
- Numbers images with captions ("1", "2", "3")
- States "put them in reverse order"
- Describes a specific sequence ("put the last one first")

In these cases, honor the user's explicit instructions.

## Common Workflows

### Multi-Document Workflow

When creating PDFs for multiple recipients from the same set of source images:

```bash
# Document A (pages 1,2,3,4,5,6)
img2pdf img1.jpg img2.jpg img3.jpg img4.jpg img5.jpg img6.jpg -o document_a.pdf

# Document B (pages 1,3,4,2,5,6 - different order)
img2pdf img1.jpg img3.jpg img4.jpg img2.jpg img5.jpg img6.jpg -o document_b.pdf
```

Each recipient gets the same pages but in their preferred order.

### Verification

After creating the PDF, verify it was created successfully:

```bash
ls -lh output.pdf && file output.pdf
```

Expected output:
```
-rw-r--r-- 1 user user 1.1M Feb 7 13:34 output.pdf
output.pdf: PDF document, version 1.3, 6 pages
```

## Output Format

The resulting PDF will:
- Contain one page per input image
- Maintain original image resolution and quality
- Use PDF version 1.3 (widely compatible)
- Have a file size similar to the sum of input images

## Troubleshooting

### Tool Not Found

If `img2pdf` is not found, install it:

```bash
python3 -m pip install --user --break-system-packages img2pdf
```

### Permission Denied

Ensure the output directory is writable and the output file doesn't have restrictive permissions.

### Wrong Page Order

If the pages are in the wrong order, the most likely cause is misunderstanding the user's intent. Go back and confirm the desired order explicitly.

## Tips

- Always confirm order when it's not explicitly stated
- Test with `file` command to verify the PDF was created successfully
- If a user says "inverse order," they mean last-to-first (6,5,4,3,2,1)
- Keep track of which filename corresponds to which user-specified page number
