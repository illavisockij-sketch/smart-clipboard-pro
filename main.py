import customtkinter as ctk
import sqlite3
import keyboard
import threading
import time
import win32clipboard
import os
import hashlib
from io import BytesIO
from PIL import Image, ImageGrab, ImageTk

class ClipboardManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Smart Clipboard Pro")
        self.geometry("500x700")
        self.attributes("-topmost", True)
        
        # Гарантированное создание путей
        self.app_path = os.path.join(os.getenv('APPDATA'), "SmartClipboard")
        self.img_path = os.path.join(self.app_path, "Screenshots")
        os.makedirs(self.img_path, exist_ok=True)

        # Подключение к БД
        db_file = os.path.join(self.app_path, "clip.db")
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS clips (content TEXT UNIQUE, type TEXT, hash TEXT)")
        self.conn.commit()

        # UI
        self.entry = ctk.CTkEntry(self, placeholder_text="🔍 Поиск...", height=40)
        self.entry.pack(fill="x", padx=15, pady=15)
        self.entry.bind("<KeyRelease>", lambda e: self.update_list())

        self.scroll = ctk.CTkScrollableFrame(self)
        self.scroll.pack(fill="both", expand=True, padx=10)

        ctk.CTkButton(self, text="🗑 Очистить историю", fg_color="#a82222", command=self.clear_all).pack(pady=15)

        self.last_hash = ""
        self.update_list()
        
        keyboard.add_hotkey("ctrl+shift+v", self.show_window)
        
        # Мониторинг в отдельном потоке
        threading.Thread(target=self.monitor_clipboard, daemon=True).start()
        
        # Показываем окно при первом запуске для теста, потом можно скрыть (self.withdraw())
        self.deiconify() 

    def get_hash(self, data):
        return hashlib.md5(data).hexdigest()

    def monitor_clipboard(self):
        while True:
            try:
                # 1. Проверка ТЕКСТА (приоритет)
                win32clipboard.OpenClipboard()
                is_text = win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT)
                text_data = None
                if is_text:
                    text_data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()

                if text_data and text_data.strip():
                    curr_hash = self.get_hash(text_data.encode('utf-16'))
                    if curr_hash != self.last_hash:
                        self.save_to_db(text_data, "text", curr_hash)
                        self.last_hash = curr_hash
                        continue # Если нашли текст, картинку не проверяем в этот цикл

                # 2. Проверка КАРТИНКИ
                img = ImageGrab.grabclipboard()
                if isinstance(img, Image.Image):
                    temp_buffer = BytesIO()
                    img.save(temp_buffer, format="PNG")
                    curr_hash = self.get_hash(temp_buffer.getvalue())
                    
                    if curr_hash != self.last_hash:
                        img_name = f"img_{int(time.time())}.png"
                        full_path = os.path.join(self.img_path, img_name)
                        img.save(full_path)
                        self.save_to_db(full_path, "image", curr_hash)
                        self.last_hash = curr_hash
            except:
                try: win32clipboard.CloseClipboard()
                except: pass
            time.sleep(0.8)

    def save_to_db(self, content, c_type, c_hash):
        self.cursor.execute("INSERT OR REPLACE INTO clips VALUES (?, ?, ?)", (content, c_type, c_hash))
        self.conn.commit()
        self.after(0, self.update_list)

    def update_list(self):
        for widget in self.scroll.winfo_children(): widget.destroy()
        self.cursor.execute("SELECT content, type FROM clips ORDER BY rowid DESC LIMIT 30")
        
        for content, c_type in self.cursor.fetchall():
            frame = ctk.CTkFrame(self.scroll, fg_color="#2b2b2b")
            frame.pack(fill="x", pady=4, padx=5)
            
            if c_type == "image":
                try:
                    img = Image.open(content)
                    img.thumbnail((100, 60))
                    tk_img = ImageTk.PhotoImage(img)
                    lbl = ctk.CTkLabel(frame, image=tk_img, text="")
                    lbl.image = tk_img 
                    lbl.pack(side="left", padx=10)
                    display_text = "📸 Скриншот"
                except: display_text = "❌ Ошибка фото"
            else:
                display_text = content[:50].replace('\n', ' ')

            btn = ctk.CTkButton(frame, text=display_text, anchor="w", fg_color="transparent",
                                 command=lambda c=content, t=c_type: self.copy_dispatch(c, t))
            btn.pack(side="left", fill="x", expand=True, padx=5)
            
            ctk.CTkButton(frame, text="✕", width=30, fg_color="#444", 
                         command=lambda c=content: self.delete_item(c)).pack(side="right", padx=5)

    def copy_dispatch(self, content, c_type):
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        if c_type == "text":
            win32clipboard.SetClipboardText(content, win32clipboard.CF_UNICODETEXT)
        else:
            img = Image.open(content)
            output = BytesIO()
            img.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        self.withdraw()

    def delete_item(self, content):
        if os.path.exists(content): os.remove(content)
        self.cursor.execute("DELETE FROM clips WHERE content=?", (content,))
        self.conn.commit()
        self.update_list()

    def clear_all(self):
        self.cursor.execute("DELETE FROM clips")
        self.conn.commit()
        for f in os.listdir(self.img_path): os.remove(os.path.join(self.img_path, f))
        self.update_list()

    def show_window(self):
        self.deiconify()
        self.focus_force()
        self.update_list()

if __name__ == "__main__":
    app = ClipboardManager()
    app.mainloop()