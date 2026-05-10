---
name: gamma
description: |
  Generate AI-powered presentations and documents using Gamma.
  Trigger phrases: "presentation", "slides", "gamma", "crear presentación", "/gamma"
---

# Gamma

This skill helps generate AI-powered presentations and documents using Gamma.app.

## Arguments

```
/gamma <type> <topic> [--style=<style>]
```

| Argument | Description | Required |
|----------|-------------|----------|
| type | presentation, document, webpage | Yes |
| topic | Subject matter or outline | Yes |
| --style | Visual style preference | No |

## Examples

```bash
/gamma presentation "Q4 2024 Sales Review"
/gamma document "Technical Architecture Overview"
/gamma webpage "Product Launch Landing Page"
/gamma presentation "React Best Practices" --style=minimal
```

## Presentation Types

### 1. Business Presentation

```bash
/gamma presentation "Quarterly Business Review" --style=corporate
```

Suggested structure:
- Executive Summary
- Key Metrics
- Achievements
- Challenges
- Next Quarter Goals
- Q&A

### 2. Technical Presentation

```bash
/gamma presentation "System Architecture Deep Dive" --style=technical
```

Suggested structure:
- Overview
- Architecture Diagram
- Components
- Data Flow
- Performance
- Security
- Future Improvements

### 3. Pitch Deck

```bash
/gamma presentation "Startup Pitch Deck" --style=startup
```

Suggested structure:
- Problem
- Solution
- Market Size
- Product Demo
- Business Model
- Traction
- Team
- Ask

## Content Generation

### 1. Define Structure

First, outline the presentation:

```markdown
# Presentation: React Best Practices

## Slides

1. **Title Slide**
   - React Best Practices 2024
   - Subtitle: Building Maintainable Applications

2. **Component Architecture**
   - Atomic design principles
   - Container vs Presentational
   - Composition over inheritance

3. **State Management**
   - When to use local state
   - Context API patterns
   - External stores (Zustand, Jotai)

4. **Performance**
   - Memoization strategies
   - Code splitting
   - Lazy loading

5. **Testing**
   - Component testing
   - Integration tests
   - E2E with Playwright

6. **Summary & Resources**
   - Key takeaways
   - Recommended reading
   - Q&A
```

### 2. Generate Content

For each slide, provide:
- Title
- Key points (3-5 bullets)
- Supporting visual (diagram, code, chart)
- Speaker notes

### 3. Export to Gamma

Options:
1. **Copy markdown** → Paste in Gamma
2. **Use Gamma API** (if available)
3. **Generate slide-by-slide** in Gamma

## Visual Styles

| Style | Description | Best For |
|-------|-------------|----------|
| corporate | Professional, clean | Business presentations |
| minimal | Simple, lots of whitespace | Technical talks |
| creative | Bold colors, unique layouts | Marketing, pitches |
| technical | Code-friendly, diagrams | Developer audiences |
| startup | Modern, energetic | Pitch decks |

## Best Practices

### Content

1. **One idea per slide** - Don't overload
2. **Use visuals** - Images > Text
3. **Keep bullets short** - 6 words max
4. **Tell a story** - Beginning, middle, end
5. **End with action** - Clear next steps

### Design

1. **Consistent fonts** - Max 2 font families
2. **Color palette** - 3-4 colors max
3. **White space** - Let content breathe
4. **Alignment** - Use grids
5. **High-quality images** - No pixelation

## Gamma.app Workflow

### 1. Access Gamma

Go to: https://gamma.app

### 2. Create New

- Click "Create new"
- Choose: Presentation, Document, or Webpage
- Enter topic/paste outline

### 3. AI Generation

- Gamma generates initial content
- Review and edit each section
- Add/remove cards as needed

### 4. Customize

- Change theme
- Adjust layouts
- Add media
- Customize fonts/colors

### 5. Share/Export

- Share link (view/edit)
- Export to PDF
- Export to PowerPoint
- Embed in websites

## Alternative: Markdown to Slides

For developers, generate markdown that can be used with:

```markdown
---
marp: true
theme: default
---

# Slide 1 Title

Content here

---

# Slide 2 Title

- Bullet 1
- Bullet 2
- Bullet 3

---

# Code Example

```javascript
const hello = () => console.log('Hello!');
```
```

Tools:
- **Marp** - Markdown to slides
- **Slidev** - Vue-powered slides
- **reveal.js** - HTML presentations

## Notes

- Gamma has a free tier with limitations
- AI-generated content should be reviewed
- Export to PowerPoint for offline editing
- Presentations can include embedded content (videos, forms)
