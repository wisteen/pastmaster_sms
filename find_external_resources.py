"""
Script to find all external resource references in templates
Run this to identify files that need fixing
"""

import os
import re
from pathlib import Path

# Patterns to search for
EXTERNAL_PATTERNS = [
    r'https?://www\.zoutula\.com',
    r'https?://.*enfant-kindergarten',
    r'src=["\']https?://(?!fonts\.googleapis|cdnjs\.cloudflare|cdn\.jsdelivr)',
    r'href=["\']https?://(?!fonts\.googleapis|cdnjs\.cloudflare|cdn\.jsdelivr)',
]

def find_external_resources(directory='templates'):
    """Find all external resource references"""
    
    print("="*60)
    print("EXTERNAL RESOURCE FINDER")
    print("="*60)
    print(f"\nSearching in: {directory}/\n")
    
    issues_found = []
    
    # Walk through all HTML files
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.html', '.htm')):
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    # Check each pattern
                    for pattern in EXTERNAL_PATTERNS:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches:
                            issues_found.append({
                                'file': filepath,
                                'pattern': pattern,
                                'matches': len(matches)
                            })
    
    # Display results
    if issues_found:
        print("⚠️  EXTERNAL RESOURCES FOUND:\n")
        
        files_with_issues = {}
        for issue in issues_found:
            file = issue['file']
            if file not in files_with_issues:
                files_with_issues[file] = []
            files_with_issues[file].append(issue)
        
        for file, issues in files_with_issues.items():
            print(f"📄 {file}")
            total_matches = sum(i['matches'] for i in issues)
            print(f"   ❌ {total_matches} external reference(s) found")
            print()
        
        print("="*60)
        print(f"TOTAL: {len(files_with_issues)} file(s) need fixing")
        print("="*60)
        
        print("\n📋 ACTION REQUIRED:")
        print("1. Review each file listed above")
        print("2. Replace external URLs with {% static '...' %}")
        print("3. Download external resources to /static/ folder")
        print("4. Remove references to www.zoutula.com")
        print("\n📖 See PERFORMANCE_FIX_GUIDE.md for details")
        
    else:
        print("✅ No external resources found!")
        print("Your templates are clean.")
    
    print("\n" + "="*60)

if __name__ == '__main__':
    find_external_resources()
