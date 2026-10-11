# Converting Static index.html to Django Template

## Challenge:
The static `index.html` is a complete standalone HTML file with:
- Full `<html>`, `<head>`, `<body>` structure
- All CSS and JavaScript inline
- Hardcoded paths to assets
- No Django template inheritance

## Solution:
We need to:
1. Extract the BODY content from index.html
2. Convert asset paths to Django `{% static %}` tags
3. Move CSS to a separate file or keep inline
4. Move JavaScript to bottom or separate file
5. Create a Django template that extends base.html
6. Preserve all the Jewels of Calvary changes

## Approach:
Since index.html is a complete WordPress theme export, we have two options:

### Option A: Use index.html as standalone (NOT extending base.html)
- Keep index.html structure as-is
- Convert paths to Django static tags
- Add Django template tags where needed
- This keeps ALL the styling and structure from index.html

### Option B: Extract content and extend base.html
- Extract only the main content sections
- Extend the existing base.html
- Lose some of the custom styling from index.html
- More work to integrate

## Recommendation:
**Option A** - Convert index.html to a standalone Django template because:
1. It has all the Jewels of Calvary customizations
2. It has the complete design we worked on
3. Less risk of breaking the layout
4. Faster implementation

## What needs to be done:
1. Replace hardcoded image paths with `{% static 'img/...' %}`
2. Replace CSS file paths with `{% static 'css/...' %}`
3. Replace JS file paths with `{% static 'js/...' %}`
4. Add `{% load static %}` at the top
5. Keep the complete HTML structure
6. This becomes a STANDALONE template, not extending base.html

Would you like me to proceed with Option A (standalone) or Option B (extending base.html)?
