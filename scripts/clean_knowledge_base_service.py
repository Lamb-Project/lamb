#!/usr/bin/env python3
import re

file_path = '/home/adrif/lamb/frontend/packages/creator-app/src/lib/services/knowledgeBaseService.js'

with open(file_path, 'r') as f:
    content = f.read()

print(f"Original file size: {len(content)} bytes")

# Pattern 1: Match the exact pattern from file
# Matches: const token = localStorage.getItem('userToken');
#          if (!token) {
#              throw new Error('User not authenticated.');
#          }
# With various spacing variations
pattern1 = r"    const token = localStorage\.getItem\('userToken'\);\s+if \(!token\) \{\s+throw new Error\('User not authenticated\.'\);\s+\}"

content_new = re.sub(pattern1, '    // Token auto-attached by apiAxios interceptor', content, flags=re.MULTILINE)
removed1 = len(re.findall(pattern1, content, flags=re.MULTILINE))
print(f"Pattern 1 matched: {removed1} times")

# Pattern 2: Clean up any leftover // Token comments to single line
pattern2 = r"    // Token auto-attached by apiAxios interceptor\s+"
content_new = re.sub(pattern2, '', content_new)

# Pattern 3: Remove "Authorization" header lines (already done but make sure)
pattern3 = r",?\s*['\"]Authorization['\"]\s*:\s*`Bearer \$\{token\}`"
content_new = re.sub(pattern3, '', content_new)

# Save the cleaned content
with open(file_path, 'w') as f:
    f.write(content_new)

print(f"New file size: {len(content_new)} bytes")
print("✓ knowledgeBaseService.js cleaned successfully")
