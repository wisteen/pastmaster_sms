# Performance & CORS Issues Fix Guide
## Jewels of Calvary Schools

**Issue**: Site loading slowly and CORS errors from external resources

---

## 🔴 CRITICAL ISSUES IDENTIFIED

### 1. **External Resource Loading**
Your site is trying to load resources from `www.zoutula.com` (demo theme site):
- Fonts (Flaticon, Revicons)
- CSS files
- JavaScript files
- Images

**Problem**: This causes:
- ❌ CORS (Cross-Origin Resource Sharing) errors
- ❌ Slow loading times
- ❌ 404 errors when demo site is down
- ❌ Dependency on external site

### 2. **home.html is Standalone**
The `templates/website/home.html` file is a complete HTML file, not using Django's template system properly.

---

## ✅ IMMEDIATE FIXES

### **FIX 1: Remove External Font References**

The site is trying to load fonts from zoutula.com. These need to be removed or replaced with local fonts.

**Files to check:**
- `templates/website/home.html`
- Any CSS files referencing external fonts

**Solution**: Use Font Awesome CDN (already included) instead of Flaticon

### **FIX 2: Use Django Template System**

Convert `home.html` to extend `base.html` like other pages.

**Current**: Standalone HTML file  
**Should be**: Django template extending base.html

### **FIX 3: Optimize Images**

Large images are slowing down the site.

**Action needed**:
1. Compress all images in `/static/img/`
2. Use WebP format for better compression
3. Implement lazy loading (already done ✅)

### **FIX 4: Remove Unnecessary Scripts**

Remove or defer non-critical JavaScript:
- WooCommerce scripts (if not using e-commerce)
- jQuery Migrate
- Unused plugins

---

## 🚀 QUICK FIX STEPS

### **STEP 1: Clean Home Page** (30 minutes)

Replace the current `home.html` with a clean Django template:

```django
{% extends 'website/base.html' %}
{% load static %}

{% block title %}Jewels of Calvary Schools | Home{% endblock %}

{% block content %}
<!-- Your content here -->
{% endblock %}
```

### **STEP 2: Remove External References** (15 minutes)

Search and remove all references to:
- `www.zoutula.com`
- `enfant-kindergarten`
- External font URLs

### **STEP 3: Use Local Resources** (15 minutes)

Ensure all resources are loaded from your own `/static/` folder:
```html
<!-- ❌ BAD -->
<link href="https://www.zoutula.com/themes/..." />

<!-- ✅ GOOD -->
<link href="{% static 'css/style.css' %}" />
```

### **STEP 4: Optimize Settings** (10 minutes)

Add to `settings.py`:

```python
# Performance Settings
SECURE_CROSS_ORIGIN_OPENER_POLICY = None  # Fix COOP warning

# Static files optimization
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Cache settings (optional)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}
```

---

## 📊 PERFORMANCE OPTIMIZATION

### **Image Optimization**

**Current Issues**:
- Images are too large (> 1MB each)
- Not compressed
- Not using modern formats

**Solutions**:

1. **Compress Images Online**:
   - Use: https://tinypng.com/
   - Or: https://squoosh.app/
   - Target: < 200KB per image

2. **Convert to WebP**:
   ```bash
   # Install cwebp (if available)
   cwebp slide1.jpg -o slide1.webp -q 80
   ```

3. **Use Responsive Images**:
   ```html
   <picture>
     <source srcset="{% static 'img/slide1.webp' %}" type="image/webp">
     <img src="{% static 'img/slide1.jpg' %}" alt="School">
   </picture>
   ```

### **CSS Optimization**

1. **Minify CSS**:
   - Remove unused CSS
   - Combine multiple CSS files
   - Use WhiteNoise compression (already enabled ✅)

2. **Critical CSS**:
   - Inline critical CSS in `<head>`
   - Defer non-critical CSS

### **JavaScript Optimization**

1. **Defer Non-Critical JS**:
   ```html
   <script src="{% static 'js/script.js' %}" defer></script>
   ```

2. **Remove Unused Scripts**:
   - jQuery Migrate (if not needed)
   - WooCommerce (if not using e-commerce)
   - Unused plugins

---

## 🔧 CORS FIX

### **Understanding CORS**

CORS errors occur when your site tries to load resources from another domain.

**Your site**: `http://jewelsofcalvaryschools.com.ng`  
**External site**: `https://www.zoutula.com`

**Solution**: Don't load external resources!

### **Fix CORS Errors**

1. **Download External Fonts**:
   - Download Flaticon fonts
   - Place in `/static/fonts/`
   - Update CSS to reference local fonts

2. **Use CDN Alternatives**:
   ```html
   <!-- Instead of Flaticon, use Font Awesome -->
   <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
   ```

3. **Add CORS Headers** (if you control the external server):
   ```python
   # In settings.py
   CORS_ALLOWED_ORIGINS = [
       "https://jewelsofcalvaryschools.com.ng",
   ]
   ```

---

## 🎯 RECOMMENDED ACTIONS

### **Priority 1: Critical (Do Now)**

1. ✅ Remove all `www.zoutula.com` references
2. ✅ Convert home.html to Django template
3. ✅ Use local resources only
4. ✅ Add COOP policy fix to settings

### **Priority 2: Important (This Week)**

1. ⚠️ Compress all images
2. ⚠️ Remove unused JavaScript
3. ⚠️ Optimize CSS
4. ⚠️ Test page speed

### **Priority 3: Nice to Have (This Month)**

1. 📌 Convert images to WebP
2. 📌 Implement browser caching
3. 📌 Add service worker for PWA
4. 📌 Use CDN for static files

---

## 📈 EXPECTED IMPROVEMENTS

### **Before Fixes**:
- ❌ Page load: 5-10 seconds
- ❌ CORS errors
- ❌ 404 errors
- ❌ Poor user experience

### **After Fixes**:
- ✅ Page load: 1-2 seconds
- ✅ No CORS errors
- ✅ No 404 errors
- ✅ Excellent user experience

---

## 🧪 TESTING

### **Test Page Speed**:
1. **Google PageSpeed Insights**:
   - URL: https://pagespeed.web.dev/
   - Target: 90+ score

2. **GTmetrix**:
   - URL: https://gtmetrix.com/
   - Target: A grade

3. **WebPageTest**:
   - URL: https://www.webpagetest.org/
   - Target: < 2 seconds load time

### **Test CORS**:
1. Open browser console (F12)
2. Check for CORS errors
3. Should see no errors after fixes

---

## 📝 QUICK CHECKLIST

- [ ] Remove www.zoutula.com references
- [ ] Convert home.html to Django template
- [ ] Use local static files only
- [ ] Add COOP policy fix
- [ ] Compress images
- [ ] Remove unused scripts
- [ ] Test page speed
- [ ] Test on mobile
- [ ] Check browser console for errors
- [ ] Verify all fonts load correctly

---

## 🆘 TROUBLESHOOTING

### **"Fonts not loading"**
- Check font files exist in `/static/fonts/`
- Verify CSS references correct path
- Clear browser cache

### **"Still seeing CORS errors"**
- Check browser console for exact URL
- Ensure no external references remain
- Clear Django cache: `python manage.py clear_cache`

### **"Site still slow"**
- Check image sizes (should be < 200KB)
- Verify WhiteNoise is enabled
- Check server response time
- Use browser dev tools Network tab

---

## 💡 PRO TIPS

1. **Use Browser DevTools**:
   - Press F12
   - Go to Network tab
   - Reload page
   - Check what's loading slowly

2. **Lazy Load Images**:
   ```html
   <img src="{% static 'img/slide1.jpg' %}" loading="lazy" alt="School">
   ```

3. **Preload Critical Resources**:
   ```html
   <link rel="preload" href="{% static 'css/main.css' %}" as="style">
   ```

4. **Use HTTP/2**:
   - Ensure your hosting supports HTTP/2
   - Faster parallel loading

---

## 📞 NEED HELP?

If issues persist:
1. Check browser console (F12) for specific errors
2. Review Django debug output
3. Check server logs in cPanel
4. Test on different browsers
5. Clear all caches (browser + Django)

---

**Created**: May 12, 2026  
**Status**: Action Required  
**Priority**: HIGH
