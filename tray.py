"""
tray.py – Icône système (barre des tâches).
Permet de montrer/cacher/quitter l'assistant depuis la barre système.
"""
import threading
import pystray
from PIL import Image, ImageDraw
import webview


def create_icon_image(size=64):
    """Génère une icône violet/noir pour la barre système."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fond circulaire sombre
    draw.ellipse([2, 2, size - 2, size - 2], fill=(15, 5, 35, 255))

    # Cercle extérieur violet
    draw.ellipse([2, 2, size - 2, size - 2], outline=(130, 60, 220, 255), width=3)

    # Croix/épée stylisée au centre
    cx, cy = size // 2, size // 2
    w = size // 3
    draw.line([(cx, cy - w), (cx, cy + w)], fill=(180, 130, 255, 255), width=3)
    draw.line([(cx - w // 2, cy - 4), (cx + w // 2, cy - 4)], fill=(180, 130, 255, 255), width=2)

    # Yeux violets
    draw.ellipse([cx - 8, cy - 4, cx - 3, cy + 1], fill=(160, 90, 255, 255))
    draw.ellipse([cx + 3, cy - 4, cx + 8, cy + 1],  fill=(160, 90, 255, 255))

    return img


def run_tray(window_ref: dict):
    """
    Lance l'icône système.
    window_ref: dict partagé {"window": webview.Window}
    """
    icon_image = create_icon_image()

    def on_show(icon, item):
        w = window_ref.get("window")
        if w:
            try: w.show()
            except: pass

    def on_hide(icon, item):
        w = window_ref.get("window")
        if w:
            try: w.hide()
            except: pass

    def on_quit(icon, item):
        icon.stop()
        w = window_ref.get("window")
        if w:
            try: w.destroy()
            except: pass

    menu = pystray.Menu(
        pystray.MenuItem('Afficher',  on_show, default=True),
        pystray.MenuItem('Masquer',   on_hide),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem('Quitter',   on_quit),
    )

    icon = pystray.Icon(
        name  = 'SungJinWoo',
        icon  = icon_image,
        title = 'Shadow Monarch',
        menu  = menu,
    )

    icon.run()


def start_tray_in_thread(window_ref: dict):
    """Lance la barre système dans un thread séparé."""
    t = threading.Thread(
        target=run_tray,
        args=(window_ref,),
        daemon=True
    )
    t.start()
    return t
