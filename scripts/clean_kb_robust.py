#!/usr/bin/env python3
"""
Limpiar knowledgeBaseService.js removiendo todas las lecturas manuales de token.
Este script usa un enfoque más robusto: línea por línea, identificando patrones específicos.
"""
import re

file_path = '/home/adrif/lamb/frontend/packages/creator-app/src/lib/services/knowledgeBaseService.js'

with open(file_path, 'r') as f:
    lines = f.readlines()

print(f"Original file: {len(lines)} lines")

output_lines = []
i = 0
removed_blocks = 0
removed_headers = 0

while i < len(lines):
    line = lines[i]
    
    # Check if this is the start of a token = localStorage.getItem block
    if "const token = localStorage.getItem('userToken')" in line:
        # This is the start of a block to remove
        # Typically followed by: if (!token) { throw ... }
        
        # Skip the const token line
        i += 1
        
        # Skip whitespace
        while i < len(lines) and lines[i].strip() == '':
            i += 1
        
        # Now we should be at the if (!token) line
        if i < len(lines) and "if (!token)" in lines[i]:
            # Skip the if line
            i += 1
            
            # Skip the {
            while i < len(lines) and '{' not in lines[i]:
                i += 1
            i += 1
            
            # Skip content until we find the closing }
            # Count braces to handle nested braces properly
            brace_count = 1
            while i < len(lines) and brace_count > 0:
                if '{' in lines[i]:
                    brace_count += lines[i].count('{')
                if '}' in lines[i]:
                    brace_count -= lines[i].count('}')
                i += 1
            
            # Add a helpful comment instead
            output_lines.append("    // Token auto-attached by apiAxios interceptor\n")
            removed_blocks += 1
            continue
    
    # Remove Authorization header lines
    if 'Authorization' in line and '`Bearer ${token}`' in line:
        removed_headers += 1
        i += 1
        continue
    
    output_lines.append(line)
    i += 1

# Write the cleaned content
with open(file_path, 'w') as f:
    f.writelines(output_lines)

print(f"Removed {removed_blocks} token blocks")
print(f"Removed {removed_headers} Authorization headers")
print(f"New file: {len(output_lines)} lines")
print("✓ knowledgeBaseService.js cleaned successfully")
