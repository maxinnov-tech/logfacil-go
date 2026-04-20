import os

for r, d, fl in os.walk('gui'):
    for f in fl:
        if not f.endswith('.py'): continue
        path = os.path.join(r, f)
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        lines = content.split('\n')
        changed = False
        
        # We need to find lines that define a CTkLabel or CTkButton that have an image= but no compound=
        # This is a bit tricky if they span multiple lines. For simplicity, we just look for "image="
        # on the same line or nearby CTkLabel calls. Actually, doing it line by line is safer for our replacements.
        for i, line in enumerate(lines):
            # Because python allows line wrapping, let's just do a simple replace on "image=" if compound isn't there
            # Since previously I inserted `image=icons.get_icon("...")` I know exactly what it looks like.
            if 'image=icons.get_icon' in line and 'compound=' not in line:
                # Add compound="left", padx=5 before image=
                lines[i] = line.replace('image=icons.get_icon', 'compound="left", padx=5, image=icons.get_icon')
                changed = True
                
        if changed:
            with open(path, 'w', encoding='utf-8') as file:
                file.write('\n'.join(lines))
            print('Updated', path)
