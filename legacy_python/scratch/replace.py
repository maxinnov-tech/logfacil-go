import os
import re

replacements = {
    '🔍 ': ('search', ''),
    '📋 ': ('clipboard', ''),
    '🗑️ ': ('trash', ''),
    '🗑 ': ('trash', ''),
    '💾 ': ('save', ''),
    '✅ ': ('checkmark', ''),
    '⚠ ': ('error', ''),
    '⚡ ': ('flash-on', ''),
    '⚙️ ': ('settings', ''),
    '📂 ': ('opened-folder', ''),
    '🎨 ': ('paint-palette', ''),
    '📍 ': ('pin', ''),
    '📊 ': ('bar-chart', ''),
    '✨ ': ('star', ''),
    '🚀 ': ('rocket', ''),
    '⬇️ ': ('download-from-cloud', ''),
    '❌ ': ('error', ''),
    '📝 ': ('edit', ''),
    '📁 ': ('opened-folder', ''),
    '📌 ': ('pin', ''),
    '🔄 ': ('restart', ''),
    '🔖 ': ('bookmark', '')
}

for r,d,fl in os.walk('gui'):
    for f in fl:
        if not f.endswith('.py'): continue
        path = os.path.join(r, f)
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
            
        original = content
        
        # Add import if missing
        if any(emoji in content for emoji in replacements.keys()):
            # Only add if it's a file that instantiates UI and actually uses the icon object
            if 'import customtkinter' in content and 'from gui.utils.icon_manager import icons' not in content:
                if 'icon_manager.py' not in path:
                    content = content.replace('import customtkinter as ctk', 'import customtkinter as ctk\nfrom gui.utils.icon_manager import icons')
                
        for emoji, (icon_name, blank) in replacements.items():
            # For menu labels just strip emoji
            pattern_menu = r'label=\"' + emoji + r'([^\"]*)\"'
            content = re.sub(pattern_menu, r'label="\1"', content)
            
            # For buttons/labels where we can add image
            pattern1 = r'text=\"' + emoji + r'([^\"]*)\"'
            content = re.sub(pattern1, r'text="\1", image=icons.get_icon("' + icon_name + r'")', content)
            
            pattern_f = r'text=f\"' + emoji + r'([^\"]*)\"'
            content = re.sub(pattern_f, r'text=f"\1", image=icons.get_icon("' + icon_name + r'")', content)

        if original != content:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(content)
            print('Updated', path)
