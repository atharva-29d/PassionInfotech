with open('backend/streaming/consumer.py', 'r') as f:
    lines = f.readlines()

new_lines = []
in_loop = False
for line in lines:
    if line.strip() == 'event = message.value':
        new_lines.append(line)
        new_lines.append('        try:\n')
        in_loop = True
        continue
    
    if in_loop:
        if line.startswith('if __name__ =='):
            new_lines.append('        except Exception as e:\n')
            new_lines.append('            print(f"ERROR: Failed to process event {event.get(\'event_id\', \'unknown\')}: {str(e)}")\n')
            new_lines.append(line)
            in_loop = False
        elif line.startswith('        ') or line == '\n':
            if line == '\n':
                new_lines.append(line)
            else:
                new_lines.append('    ' + line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open('backend/streaming/consumer.py', 'w') as f:
    f.writelines(new_lines)
