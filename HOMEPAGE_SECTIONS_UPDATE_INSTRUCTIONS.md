# Homepage Sections Update Instructions

## Date: May 9, 2026

## Summary
Instructions to remove "WHAT'S NEW" section and replace statistics section with "UPCOMING BIRTHDAYS" linked to backend.

---

## TASK 1: Remove "WHAT'S NEW" Section

### Location in home.html:
Search for: `<h2 style="color:;" class=" ztl-accent-font ztl-center ztl-font-normal">WHAT'S NEW</h2>`

### What to Remove:
Remove everything from:
```html
<div class="vc_row wpb_row vc_row-fluid"><div class="wpb_column vc_column_container vc_col-sm-12"><div class="vc_column-inner vc_custom_1490041163163"><div class="wpb_wrapper"><div class="vc_empty_space"   style="height: 50px"><span class="vc_empty_space_inner"></span></div><h2 style="color:;" class=" ztl-accent-font ztl-center ztl-font-normal">WHAT'S NEW</h2>
```

To (and including):
```html
<div class="vc_btn3-container  ztl-button-one vc_btn3-center vc_custom_1486919918695" ><a class="vc_general vc_btn3 vc_btn3-size-md vc_btn3-shape-round vc_btn3-style-outline vc_btn3-color-danger" href="#" title="">GO TO BLOG</a></div><div class="vc_empty_space"   style="height: 60px"><span class="vc_empty_space_inner"></span></div></div></div></div></div>
```

This includes:
- "WHAT'S NEW" heading
- "Keep up to date with the latest news" subtitle
- Divider
- Blog posts grid (Essential Grid)
- "GO TO BLOG" button
- All associated styles and JavaScript

---

## TASK 2: Replace Statistics Section with Upcoming Birthdays

### Location in home.html:
Search for: `<div class="description" style="color:#ffffff">Outdoor Activities</div>`

### What to Replace:
Replace the entire section from:
```html
<div data-vc-full-width="true" data-vc-full-width-init="false" data-vc-parallax="3" data-vc-parallax-image="https://www.zoutula.com/themes/enfant-kindergarten/wp-content/uploads/2017/03/kids-playing.jpg" class="vc_row wpb_row vc_row-fluid vc_custom_1490463771135 vc_row-has-fill vc_general vc_parallax vc_parallax-content-moving">
```

To (and including):
```html
</div></div></div></div></div><div class="vc_row-full-width vc_clearfix"></div>
```

This section contains:
- 75 Outdoor Activities
- 237 Sleep Stories
- 32 Loving Teachers
- 457 Pencils Wood

### Replace With:
Use the content from `UPCOMING_BIRTHDAYS_SECTION.html` file

---

## NEW UPCOMING BIRTHDAYS SECTION

### Features:
✅ Displays up to 5 upcoming birthdays (next 30 days)
✅ Shows student name, class, birthday date
✅ Shows days until birthday
✅ Special indicator for "Today" and "Tomorrow"
✅ Alternating orange (#ff8d00) and teal (#53b6bc) colors
✅ Cake icon for each birthday
✅ Responsive grid layout
✅ Empty state when no birthdays
✅ Linked to Django backend via `upcoming_birthdays` context

### Data Source:
- **View**: `website/views.py` → `home()` function
- **Context Variable**: `upcoming_birthdays`
- **Model**: `core.models.Student`
- **Fields Used**: `user.get_full_name()`, `date_of_birth`, `school_class.name`

### Backend Logic (Already Implemented):
```python
# Get upcoming birthdays from students
today = timezone.now().date()
upcoming_birthdays = []

students = Student.objects.select_related('user', 'school_class').all()
for student in students:
    if student.date_of_birth:
        birthday_this_year = student.date_of_birth.replace(year=today.year)
        if birthday_this_year < today:
            birthday_this_year = birthday_this_year.replace(year=today.year + 1)
        days_until = (birthday_this_year - today).days
        if 0 <= days_until <= 30:
            upcoming_birthdays.append({
                'name': student.user.get_full_name(),
                'date': birthday_this_year,
                'days_until': days_until,
                'class': student.school_class.name
            })

upcoming_birthdays.sort(key=lambda x: x['days_until'])
upcoming_birthdays = upcoming_birthdays[:5]
```

---

## MANUAL STEPS TO COMPLETE

### Step 1: Open home.html
```
c:\Users\HomePC\Music\truecalms\templates\website\home.html
```

### Step 2: Remove "WHAT'S NEW" Section
1. Search for: `WHAT'S NEW`
2. Find the opening `<div class="vc_row wpb_row vc_row-fluid">` before it
3. Delete everything until (and including) the `GO TO BLOG` button and its closing divs
4. This should remove approximately 200+ lines of code

### Step 3: Replace Statistics Section
1. Search for: `Outdoor Activities`
2. Find the opening `<div data-vc-full-width="true"...vc_custom_1490463771135...>`
3. Delete the entire section (4 counter columns)
4. Paste the content from `UPCOMING_BIRTHDAYS_SECTION.html`

### Step 4: Save and Test
1. Save the file
2. Refresh the homepage
3. Verify:
   - "WHAT'S NEW" section is gone
   - Statistics counters are gone
   - "UPCOMING BIRTHDAYS" section appears
   - Birthdays display correctly (if any students have birthdays in next 30 days)

---

## TESTING CHECKLIST

### Visual Check:
- [ ] "WHAT'S NEW" section removed
- [ ] Blog posts grid removed
- [ ] "GO TO BLOG" button removed
- [ ] Statistics counters removed (75, 237, 32, 457)
- [ ] "UPCOMING BIRTHDAYS" heading displays
- [ ] Birthday cards display (if data exists)
- [ ] Empty state displays (if no birthdays)

### Functionality Check:
- [ ] Birthday data pulls from database
- [ ] Student names display correctly
- [ ] Class names display correctly
- [ ] Birthday dates display correctly
- [ ] "Days until" calculation is accurate
- [ ] "Today" shows for current birthdays
- [ ] "Tomorrow" shows for next-day birthdays
- [ ] Maximum 5 birthdays show
- [ ] Only birthdays within 30 days show

### Responsive Check:
- [ ] Desktop: Grid layout works
- [ ] Tablet: Cards stack appropriately
- [ ] Mobile: Single column layout
- [ ] All text is readable
- [ ] Icons display correctly

---

## DESIGN SPECIFICATIONS

### Colors:
- **Primary Orange**: #ff8d00
- **Secondary Teal**: #53b6bc
- **White Background**: rgba(255, 255, 255, 0.95)
- **Text Dark**: #333
- **Text Medium**: #666
- **Text Light**: #999

### Typography:
- **Heading**: 42px, Montserrat, bold, white
- **Subtitle**: 18px, Lato, white
- **Student Name**: 18px, Montserrat, bold, #333
- **Class**: 14px, Lato, #666
- **Date**: 16px, Lato, bold, #ff8d00
- **Days Until**: 13px, Lato, #999

### Layout:
- **Grid**: Auto-fit, minimum 250px columns
- **Gap**: 25px
- **Max Width**: 1200px
- **Card Padding**: 25px
- **Border Radius**: 15px
- **Icon Size**: 70px circle, 40px icon

### Icons:
- **Birthday**: `cake` (Material Symbols)
- **Empty State**: `celebration` (Material Symbols)

---

## BACKEND DATA REQUIREMENTS

### To Display Birthdays:
1. Students must exist in database
2. Students must have `date_of_birth` set
3. Students must be linked to a `school_class`
4. Students must have a `user` with first_name and last_name

### To Test:
1. Go to Django admin
2. Add/edit students
3. Set `date_of_birth` to dates within next 30 days
4. Ensure students have class assigned
5. Refresh homepage to see birthdays

---

## TROUBLESHOOTING

### No Birthdays Showing:
- Check if students have `date_of_birth` set
- Verify dates are within next 30 days
- Check if students are linked to classes
- Verify `upcoming_birthdays` is in context

### Layout Issues:
- Check Material Icons CDN is loaded
- Verify grid CSS is not conflicting
- Check browser console for errors

### Data Not Updating:
- Clear Django cache
- Restart development server
- Check database for student data
- Verify view logic is correct

---

## FILES TO REFERENCE

1. **UPCOMING_BIRTHDAYS_SECTION.html**
   - Contains the complete HTML for new section
   - Copy and paste this into home.html

2. **website/views.py**
   - Contains backend logic (already implemented)
   - No changes needed

3. **templates/website/home.html**
   - Main file to edit
   - Remove "WHAT'S NEW" section
   - Replace statistics section

---

## ESTIMATED TIME
- Remove "WHAT'S NEW": 5 minutes
- Replace statistics: 5 minutes
- Testing: 10 minutes
- **Total**: 20 minutes

---

**Status**: Ready for implementation
**Priority**: High
**Complexity**: Medium
