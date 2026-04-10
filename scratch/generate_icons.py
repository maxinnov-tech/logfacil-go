import os
from PIL import Image, ImageDraw

def create_icon(name, color, type_shape):
    size = (64, 64)
    img = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    if type_shape == "dashboard":
        # Um quadrado de 4 blocos
        draw.rectangle([10, 10, 30, 30], fill=color)
        draw.rectangle([34, 10, 54, 30], fill=color)
        draw.rectangle([10, 34, 30, 54], fill=color)
        draw.rectangle([34, 34, 54, 54], fill=color)
    elif type_shape == "logs":
        # Linhas de texto
        draw.rectangle([10, 15, 54, 20], fill=color)
        draw.rectangle([10, 25, 45, 30], fill=color)
        draw.rectangle([10, 35, 54, 40], fill=color)
        draw.rectangle([10, 45, 35, 50], fill=color)
    elif type_shape == "pdv":
        # Ícone de monitor/terminal
        draw.rectangle([10, 15, 54, 45], outline=color, width=3)
        draw.rectangle([25, 45, 39, 52], fill=color)
        draw.rectangle([15, 52, 49, 55], fill=color)
    elif type_shape == "settings":
        # Círculo/Engrenagem simples
        draw.ellipse([15, 15, 49, 49], outline=color, width=4)
        draw.ellipse([27, 27, 37, 37], fill=color)
    elif type_shape == "restart":
        # Seta circular (Simplificada)
        draw.arc([15, 15, 49, 49], start=0, end=270, fill=color, width=4)
        draw.polygon([45, 10, 55, 20, 45, 30], fill=color)
    elif type_shape == "pause":
        # Duas barras
        draw.rectangle([20, 15, 28, 49], fill=color)
        draw.rectangle([36, 15, 44, 49], fill=color)
    elif type_shape == "play":
        # Triângulo
        draw.polygon([20, 15, 50, 32, 20, 49], fill=color)
    
    path = f"assets/icons/{name}.png"
    img.save(path)
    print(f"Icon saved: {path}")

os.makedirs("assets/icons", exist_ok=True)
create_icon("dashboard", "#3498db", "dashboard")
create_icon("logs", "#3498db", "logs")
create_icon("pdv", "#3498db", "pdv")
create_icon("settings", "#3498db", "settings")
create_icon("restart", "#FFFFFF", "restart")
create_icon("pause", "#FFFFFF", "pause")
create_icon("play", "#FFFFFF", "play")
