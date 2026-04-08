import customtkinter as ctk

class LoadingSpinner:
    def __init__(self, parent, text="Carregando"):
        self.parent = parent
        self.frame = None
        self.label = None
        self.text = text
        self.is_visible = False
        self._dot_count = 0
        self._after_id = None
        self._animation_running = False
        self.spinner_label = None
        
    def show(self):
        if self.is_visible:
            return
            
        self.is_visible = True
        self._animation_running = True
        self._dot_count = 0
        
        self.frame = ctk.CTkFrame(self.parent, fg_color="#2b2b2b", corner_radius=15, width=280, height=100)
        self.frame.place(relx=0.5, rely=0.5, anchor="center")
        self.frame.pack_propagate(False)
        
        inner_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        inner_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        self.spinner_label = ctk.CTkLabel(inner_frame, text="◐", font=ctk.CTkFont(size=30), text_color="#4CAF50")
        self.spinner_label.pack(pady=(0, 10))
        
        self.label = ctk.CTkLabel(inner_frame, text=self.text, font=ctk.CTkFont(size=12), text_color="#888888")
        self.label.pack()
        
        self._animate_spinner()
        self._animate_text()
        
    def _animate_spinner(self):
        if not self._animation_running or not self.is_visible or not self.spinner_label:
            return
        
        chars = ["◐", "◓", "◑", "◒"]
        current_char = self.spinner_label.cget("text")
        try:
            next_index = (chars.index(current_char) + 1) % len(chars)
        except ValueError:
            next_index = 0
        
        self.spinner_label.configure(text=chars[next_index])
        self._after_id = self.spinner_label.after(100, self._animate_spinner)
        
    def _animate_text(self):
        if not self._animation_running or not self.is_visible or not self.label:
            return
        
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self.label.configure(text=f"{self.text}{dots}")
        self.label.after(500, self._animate_text)
        
    def hide(self):
        self._animation_running = False
        self.is_visible = False
        
        if self._after_id and self.spinner_label:
            try:
                self.spinner_label.after_cancel(self._after_id)
            except Exception:
                pass
        
        if self.frame and self.frame.winfo_exists():
            self.frame.destroy()
            self.frame = None
            
    def update_text(self, text):
        self.text = text
