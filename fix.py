import sys
with open('domain/services/solver.py', 'r') as f:
    content = f.read()
content = content.replace('</content>', '')
with open('domain/services/solver.py', 'w') as f:
    f.write(content)
print('Fixed')