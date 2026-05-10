---
name: excalidraw-flowchart
description: |
  Create flowcharts and diagrams from text descriptions using Excalidraw format.
  Trigger phrases: "flowchart", "diagram", "excalidraw", "/excalidraw-flowchart"
---

# Excalidraw Flowchart

This skill creates flowcharts and diagrams from text descriptions, generating Excalidraw-compatible JSON that can be imported into Excalidraw.

## Arguments

```
/excalidraw-flowchart <description>
```

| Argument | Description | Required |
|----------|-------------|----------|
| description | Text description of the flowchart | Yes |

## Examples

```bash
/excalidraw-flowchart "user login flow: start -> enter credentials -> validate -> success/failure -> dashboard or error"

/excalidraw-flowchart "API request lifecycle: client -> load balancer -> api gateway -> microservice -> database -> response"

/excalidraw-flowchart "git workflow: feature branch -> PR -> review -> merge -> deploy"
```

## Diagram Types

### 1. Flowchart

```
/excalidraw-flowchart "flowchart: start -> process -> decision [yes/no] -> end"
```

### 2. Sequence Diagram

```
/excalidraw-flowchart "sequence: user -> frontend -> backend -> database"
```

### 3. Architecture Diagram

```
/excalidraw-flowchart "architecture: [client] -> [cdn] -> [load balancer] -> [app servers] -> [database cluster]"
```

### 4. State Machine

```
/excalidraw-flowchart "states: idle -> loading -> success/error -> idle"
```

## Output Format

The skill generates an Excalidraw JSON file that can be:
1. Imported directly into excalidraw.com
2. Saved as `.excalidraw` file
3. Embedded in documentation

### Example Output

```json
{
  "type": "excalidraw",
  "version": 2,
  "source": "claude-code",
  "elements": [
    {
      "type": "rectangle",
      "x": 100,
      "y": 100,
      "width": 120,
      "height": 60,
      "strokeColor": "#1e1e1e",
      "backgroundColor": "#a5d8ff",
      "fillStyle": "solid",
      "strokeWidth": 2,
      "roundness": { "type": 3 }
    },
    {
      "type": "text",
      "x": 130,
      "y": 120,
      "text": "Start",
      "fontSize": 16,
      "fontFamily": 1
    },
    {
      "type": "arrow",
      "x": 220,
      "y": 130,
      "width": 80,
      "height": 0,
      "strokeColor": "#1e1e1e",
      "strokeWidth": 2,
      "points": [[0, 0], [80, 0]]
    }
  ],
  "appState": {
    "viewBackgroundColor": "#ffffff"
  }
}
```

## Shape Reference

| Shape | Use For |
|-------|---------|
| Rectangle | Processes, actions |
| Diamond | Decisions |
| Ellipse | Start/End points |
| Parallelogram | Input/Output |
| Arrow | Flow direction |
| Line | Connections |

## Color Palette

| Color | Hex | Use |
|-------|-----|-----|
| Blue | #a5d8ff | Primary actions |
| Green | #b2f2bb | Success states |
| Red | #ffc9c9 | Error states |
| Yellow | #ffec99 | Warnings/decisions |
| Gray | #e9ecef | Neutral states |
| Purple | #d0bfff | Special processes |

## Layout Algorithm

1. **Parse description** - Extract nodes and connections
2. **Calculate positions** - Arrange left-to-right or top-to-bottom
3. **Size elements** - Based on text content
4. **Draw connections** - Add arrows between nodes
5. **Apply styling** - Colors, stroke width, roundness

## Usage Workflow

### 1. Generate Diagram

```bash
/excalidraw-flowchart "checkout: cart -> shipping -> payment -> confirmation"
```

### 2. Save Output

Save the JSON to a file:
```bash
# Save as .excalidraw file
cat > checkout-flow.excalidraw << 'EOF'
{ ... generated JSON ... }
EOF
```

### 3. Open in Excalidraw

- Go to excalidraw.com
- File > Open
- Select the .excalidraw file
- Edit and refine as needed

### 4. Export

- Export as PNG/SVG for documentation
- Embed in markdown
- Share collaboration link

## Tips

1. **Keep it simple** - Start with main flow, add details later
2. **Use consistent naming** - Match code/feature names
3. **Add decision branches** - Use `[yes/no]` or `[success/failure]`
4. **Group related items** - Use containers for subsystems
5. **Color code** - Use colors to indicate status or type

## Integration

### Embed in README

```markdown
![Checkout Flow](./diagrams/checkout-flow.png)
```

### Link to Excalidraw

```markdown
[Edit Diagram](https://excalidraw.com/#json=...)
```

## Notes

- Excalidraw is open source and self-hostable
- JSON format is human-readable and version-controllable
- Supports collaboration via shareable links
- Can export to PNG, SVG, or embed in Notion/Confluence
