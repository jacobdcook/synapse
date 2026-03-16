import re

def test_filename_detection():
    # Simulate the context around a code block
    contexts = [
        "```python:main.py\nprint('hello')\n```",
        "Save this to 'utils/helper.py' and run it.",
        "The code in File: database.py is updated.",
        "Check out `config.json` for details.",
        "```javascript\n// No filename here\n```"
    ]
    
    results = []
    for context in contexts:
        path_match = None
        # 1. Look for language block filename pattern: ```python:main.py
        lang_line = context.split('\n')[0]
        path_match = re.search(r'[:/]([\w\-/._]+\.\w+)', lang_line)
        
        # 2. Search for common path patterns in context
        if not path_match:
            path_match = re.search(r'[`"\' ]([\w\-/._]+\.\w+)[`"\' ]', context)
            if path_match: print(f"  Debug context match: {path_match.group(0)}")
        
        # 3. Also look for "File: path" or "in path"
        if not path_match:
            path_match = re.search(r'(?:[Ff]ile|[Ii]n):?\s*([\w\-/._]+\.\w+)', context)
            if path_match: print(f"  Debug File/In match: {path_match.group(0)}")
        
        path = path_match.group(1) if path_match else None
        results.append(path)
    
    expected = ["main.py", "utils/helper.py", "database.py", "config.json", None]
    for i, (res, exp) in enumerate(zip(results, expected)):
        print(f"Test {i}: Detected={res}, Expected={exp} - {'PASS' if res == exp else 'FAIL'}")

if __name__ == "__main__":
    test_filename_detection()
