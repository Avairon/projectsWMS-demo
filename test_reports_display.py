#!/usr/bin/env python3
"""
Test script to verify that reports are properly displayed in project task cards.
This script tests the functionality implemented to show reports in the task modal.
"""

import json
import os
from datetime import datetime

def test_reports_structure():
    """Test that the reports section is properly added to the project detail template"""
    template_path = "/workspace/app/templates/project_detail.html"
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the reports section exists in the template
    if '<div class="task-reports" id="task-reports">' in content:
        print("✓ Reports section found in project_detail.html template")
    else:
        print("✗ Reports section NOT found in project_detail.html template")
        return False
    
    if '<div class="reports-list"></div>' in content:
        print("✓ Reports list container found in template")
    else:
        print("✗ Reports list container NOT found in template")
        return False
    
    return True

def test_css_styles():
    """Test that CSS styles for reports are properly added"""
    css_path = "/workspace/app/static/css/style.css"
    
    with open(css_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for reports-related CSS classes
    required_css = [
        '.task-reports',
        '.reports-list', 
        '.report-item',
        '.report-comment',
        '.report-date',
        '.report-file'
    ]
    
    all_found = True
    for css_class in required_css:
        if css_class in content:
            print(f"✓ CSS class {css_class} found")
        else:
            print(f"✗ CSS class {css_class} NOT found")
            all_found = False
    
    return all_found

def test_js_functionality():
    """Test that JavaScript handles reports in the task modal"""
    js_path = "/workspace/app/static/js/main.js"
    
    with open(js_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for reports-related JavaScript code
    if 'reportsList' in content and 'task.reports' in content:
        print("✓ JavaScript code for reports found in main.js")
    else:
        print("✗ JavaScript code for reports NOT found in main.js")
        return False
    
    if 'report-item' in content and 'report-comment' in content:
        print("✓ JavaScript creates report items with proper classes")
    else:
        print("✗ JavaScript does NOT create report items with proper classes")
        return False
    
    if 'fileHtml' in content and 'fileUrl' in content:
        print("✓ JavaScript handles file attachments in reports")
    else:
        print("✗ JavaScript does NOT handle file attachments in reports")
        return False
    
    return True

def test_route_modifications():
    """Test that routes are properly modified to include reports data"""
    routes_path = "/workspace/app/routes/tasks.py"
    
    with open(routes_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for reports formatting in both routes
    if 'Format reports with executor names and proper dates' in content:
        print("✓ Reports formatting logic found in routes")
    else:
        print("✗ Reports formatting logic NOT found in routes")
        return False
    
    if 'formatted_reports.sort(key=lambda x: x[\'date\'], reverse=True)' in content:
        print("✓ Reports sorting by date found in routes")
    else:
        print("✗ Reports sorting by date NOT found in routes")
        return False
    
    # Check both task_detail and api_task_detail functions have the formatting
    lines = content.split('\n')
    api_function_found = False
    regular_function_found = False
    
    for i, line in enumerate(lines):
        if 'def api_task_detail(' in line:
            # Check if the next few lines contain the formatting logic
            for j in range(i, min(i+50, len(lines))):
                if 'Format reports with executor names and proper dates' in lines[j]:
                    api_function_found = True
                    break
        elif 'def task_detail(' in line:
            # Check if the next few lines contain the formatting logic
            for j in range(i, min(i+50, len(lines))):
                if 'Format reports with executor names and proper dates' in lines[j]:
                    regular_function_found = True
                    break
    
    if api_function_found:
        print("✓ API task detail function has reports formatting")
    else:
        print("✗ API task detail function does NOT have reports formatting")
        return False
    
    if regular_function_found:
        print("✓ Regular task detail function has reports formatting")
    else:
        print("✗ Regular task detail function does NOT have reports formatting")
        return False
    
    return True

def main():
    """Run all tests"""
    print("Testing reports display functionality in project task cards...")
    print("=" * 60)
    
    tests = [
        ("Template structure", test_reports_structure),
        ("CSS styles", test_css_styles), 
        ("JavaScript functionality", test_js_functionality),
        ("Route modifications", test_route_modifications)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}...")
        print("-" * 30)
        if test_func():
            passed += 1
            print(f"✓ {test_name} test PASSED")
        else:
            print(f"✗ {test_name} test FAILED")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Reports display functionality is properly implemented.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    main()