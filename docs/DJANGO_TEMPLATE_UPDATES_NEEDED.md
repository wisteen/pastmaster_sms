# Django Template Updates for Jewels of Calvary Schools

## Files to Update:
1. `templates/website/home.html` - Main homepage template
2. `templates/website/base.html` - Base template (for school name, meta tags, etc.)

## Changes Needed in `base.html`:

### 1. School Name & Branding
- Replace "Thy Kingdom Come Schools" with "Jewels of Calvary Schools"
- Update tagline to: "Raising Wholesome Children Globally Relevant for the Future"
- Update all meta descriptions and titles

### 2. Contact Information
- Phone: +234 123 456 7890
- Email: info@jewelsofcalvary.edu.ng
- Address: 123 Education Street, Lagos, Nigeria
- School Hours: Mon - Fri: 7:30 AM - 3:00 PM

### 3. SEO & Meta Tags
- Update all references from "Thy Kingdom Come" to "Jewels of Calvary"
- Update keywords to include "Jewels of Calvary Schools"
- Update canonical URLs
- Update Open Graph tags
- Update Twitter Card tags
- Update structured data (JSON-LD)

## Changes Needed in `home.html`:

### 1. Hero Slider
- Keep the slider structure but update text overlays
- Hide text on mobile screens (add CSS media query)
- Remove navigation arrows (already done in static version)
- Make slider responsive with autoHeight

### 2. Feature Icons Section
- Convert all icons to Material Icons (Google Material Symbols Outlined)
- Remove flaticon references
- Update icon CDN links in base template

### 3. About Section
- Update welcome text for Jewels of Calvary Schools
- Update principal/director message
- Update school description

### 4. Stats Section
- Update statistics to match Jewels of Calvary Schools
- Keep the counter animation

### 5. Gallery Section
- Keep Django template loop for gallery images
- Ensure Material Icons are used for zoom/view icons

### 6. School Calendar Section (NEW)
- Add new section with three terms:
  * First Term: Sept 9 - Dec 13, 2024
  * Second Term: Jan 6 - Apr 4, 2025
  * Third Term: Apr 28 - Jul 18, 2025
- Add special events:
  * Parents' Day: November 15, 2024
  * Sports Day: March 14, 2025
  * Cultural Day: May 23, 2025
  * Graduation: July 11, 2025
- Use Material Icons for event icons

### 7. Remove Sections
- Remove "PLAN UPGRADES" / Pricing section (if exists)
- Remove "Want to Hear From Us?" newsletter section (keep only footer newsletter)

### 8. Footer Updates
- Update school information
- Remove social media icons
- Remove icon decorations from lists (location, phone, email, schedule icons)
- Remove arrow icons from Quick Links
- Add "Powered by Educeptis Africa Limited" link
- Update copyright to "© 2024 Jewels of Calvary Schools"

### 9. Material Icons Implementation
Add to base.html <head>:
```html
<!-- Material Icons CDN -->
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" />
```

Add CSS for Material Icons:
```css
/* Material Icons styling */
.material-symbols-outlined {
    font-family: 'Material Symbols Outlined' !important;
    font-weight: normal;
    font-style: normal;
    font-size: 24px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    -webkit-font-smoothing: antialiased;
}

/* Scroll to top button icon */
.ztl-scroll-top .material-symbols-outlined {
    font-size: 28px !important;
    line-height: 1 !important;
    vertical-align: middle !important;
}
```

### 10. Mobile Responsive CSS
Add media queries for hero section:
```css
/* Mobile responsive for hero section */
@media only screen and (max-width: 767px) {
    .rs-layer {
        display: none !important;
    }
}

@media only screen and (max-width: 480px) {
    .rs-layer {
        display: none !important;
    }
}
```

### 11. Icon Mappings (Flaticon to Material Icons)
Replace all flaticon classes with Material Icons:
- flaticon-location-2 → location_on
- flaticon-clock-2 → schedule
- flaticon-body → child_care
- flaticon-abc-block → abc
- flaticon-school-material → school
- flaticon-construction → construction
- flaticon-wind → air
- flaticon-puzzle → extension
- flaticon-doll-1 → toys
- flaticon-food → restaurant
- flaticon-train → train
- flaticon-plane → flight
- base-flaticon-signs → zoom_in
- base-flaticon-search → search
- base-flaticon-bag → shopping_bag

### 12. Scroll-to-Top Button
Update from Font Awesome to Material Icons:
```html
<a href="#" class="ztl-scroll-top">
    <span class="material-symbols-outlined">keyboard_arrow_up</span>
</a>
```

## Implementation Steps:

1. **Backup current templates** before making changes
2. **Update base.html** with school branding and Material Icons CDN
3. **Update home.html** with all content changes
4. **Test on development server** to ensure Django template tags work
5. **Check responsive design** on mobile devices
6. **Verify all icons display** correctly
7. **Test all links** and navigation
8. **Check SEO meta tags** are correct

## Django-Specific Considerations:

- Keep all `{% %}` template tags intact
- Keep all `{{ }}` variable references
- Maintain `{% load static %}` at the top
- Keep `{% url %}` tags for navigation
- Preserve `{% csrf_token %}` in forms
- Keep template loops like `{% for %}` and `{% endfor %}`
- Maintain conditional tags like `{% if %}` and `{% empty %}`

## Static Files:

Ensure these are in the static folder:
- Logo: `static/img/logo.png`
- Slider images: `static/img/slide1.jpg`, `slide2.jpg`, etc.
- School photos for gallery
- CSS files with Material Icons styling
- JavaScript files for slider and animations

## Database Models to Check:

- Gallery images model (for dynamic gallery)
- News/Posts model (for news section)
- Newsletter subscription model
- Any other dynamic content models

Would you like me to proceed with updating the actual Django template files now?
