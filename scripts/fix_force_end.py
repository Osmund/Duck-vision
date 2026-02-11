#!/usr/bin/env python3
"""Fix force_end IndentationError in duck_ai.py on Pi 4."""

ai_file = '/home/admog/Code/chatgpt-and/src/duck_ai.py'
with open(ai_file, 'r') as f:
    lines = f.readlines()

# Find the broken block (around line 2600-2620)
# Looking for "if force_end:" inside "# Vi har et vanlig text-svar"
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if '# Vi har et vanlig text-svar' in line:
        start_idx = i
    if start_idx and i > start_idx and 'break' in line and line.strip() == 'break':
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print(f"Could not find block: start={start_idx}, end={end_idx}")
    # Try to find the area
    for i, line in enumerate(lines):
        if 2595 <= i <= 2625:
            print(f"{i+1}: {line.rstrip()}")
    exit(1)

# Get the indentation from the "text-svar" comment line
base_indent = '                '  # 16 spaces (4 levels of 4)

# Build the replacement block
replacement = [
    base_indent + '# Vi har et vanlig text-svar\n',
    base_indent + 'if force_end:\n',
    base_indent + '    # Overstyr GPTs lange svar - bruk kort sang-beskjed\n',
    base_indent + '    import re as _re\n',
    base_indent + '    reply_content = None\n',
    base_indent + '    for msg in reversed(final_messages):\n',
    base_indent + '        if msg.get("role") == "tool":\n',
    base_indent + '            tool_result = msg.get("content", "")\n',
    base_indent + '            m = _re.search(r"SANG LAGET: (.+?)\\\\.", tool_result)\n',
    base_indent + '            if m:\n',
    base_indent + '                reply_content = f"N\\u00e5 synger jeg {m.group(1)} for deg!"\n',
    base_indent + '            else:\n',
    base_indent + '                reply_content = "N\\u00e5 synger jeg for deg!"\n',
    base_indent + '            break\n',
    base_indent + '    if not reply_content:\n',
    base_indent + '        reply_content = "N\\u00e5 synger jeg for deg!"\n',
    base_indent + '    print(f"force_end: Overstyrte GPT-svar med: {reply_content}", flush=True)\n',
    base_indent + 'else:\n',
    base_indent + '    reply_content = message2.get("content")\n',
    base_indent + 'break\n',
]

# Replace lines from start_idx to end_idx (inclusive)
new_lines = lines[:start_idx] + replacement + lines[end_idx+1:]

with open(ai_file, 'w') as f:
    f.writelines(new_lines)

print(f"OK: Replaced lines {start_idx+1}-{end_idx+1} with {len(replacement)} lines")

# Verify syntax
import py_compile
try:
    py_compile.compile(ai_file, doraise=True)
    print("Syntax OK!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
