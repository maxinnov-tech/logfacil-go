import tkinter as tk
import customtkinter as ctk

class IncrementalSearch:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.search_frame = None
        self.search_entry = None
        self.search_term = ""
        self.current_position = 0
        self.matches = []
        self.case_sensitive = False
        self.case_var = None
        
    def show_search_bar(self):
        if self.search_frame and self.search_frame.winfo_exists():
            self.search_frame.destroy()
            
        self.search_frame = ctk.CTkFrame(self.text_widget.master, height=40, fg_color="#3c3c3c")
        self.search_frame.pack(side="top", fill="x", padx=5, pady=(0, 5))
        self.search_frame.pack_propagate(False)
        
        ctk.CTkLabel(self.search_frame, text="🔍 Buscar:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(10, 5))
        
        self.search_entry = ctk.CTkEntry(self.search_frame, width=300, placeholder_text="Digite para buscar...")
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", self.on_search_change)
        self.search_entry.bind("<Return>", self.search_next)
        self.search_entry.bind("<Shift-Return>", self.search_prev)
        self.search_entry.bind("<Escape>", lambda e: self.hide_search_bar())
        
        btn_prev = ctk.CTkButton(self.search_frame, text="▲", width=30, height=30, command=self.search_prev)
        btn_prev.pack(side="left", padx=2)
        
        btn_next = ctk.CTkButton(self.search_frame, text="▼", width=30, height=30, command=self.search_next)
        btn_next.pack(side="left", padx=2)
        
        self.count_label = ctk.CTkLabel(self.search_frame, text="0/0", font=ctk.CTkFont(size=11))
        self.count_label.pack(side="left", padx=10)
        
        btn_close = ctk.CTkButton(self.search_frame, text="✕", width=30, height=30, fg_color="#d9534f",
                                   hover_color="#c9302c", command=self.hide_search_bar)
        btn_close.pack(side="right", padx=5)
        
        self.case_var = tk.BooleanVar(value=False)
        case_check = ctk.CTkCheckBox(self.search_frame, text="Diferenciar maiúsculas",
                                      variable=self.case_var, command=self.on_search_change)
        case_check.pack(side="right", padx=10)
        
        self.search_entry.focus_set()
        
    def hide_search_bar(self):
        if self.search_frame:
            self.search_frame.destroy()
            self.search_frame = None
            self.clear_highlights()
            self.text_widget.focus_set()
            
    def on_search_change(self, event=None):
        self.search_term = self.search_entry.get()
        self.clear_highlights()
        
        if not self.search_term:
            self.matches = []
            self.current_position = 0
            self.count_label.configure(text="0/0")
            return
            
        self.find_all_matches()
        self.highlight_matches()
        self.update_count_label()
        
        if self.matches:
            self.current_position = 0
            self.goto_match(0)
            
    def find_all_matches(self):
        self.matches = []
        self.text_widget.configure(state="normal")
        
        search_kwargs = {'nocase': not self.case_var.get(), 'regexp': False}
        start = "1.0"
        
        while True:
            pos = self.text_widget.search(self.search_term, start, stopindex="end", **search_kwargs)
            if not pos:
                break
            end = f"{pos}+{len(self.search_term)}c"
            self.matches.append((pos, end))
            start = end
            
        self.text_widget.configure(state="disabled")
        
    def highlight_matches(self):
        self.text_widget.configure(state="normal")
        self.text_widget.tag_delete("search_highlight")
        self.text_widget.tag_config("search_highlight", background="#FFD700", foreground="#000000")
        self.text_widget.tag_delete("current_match")
        self.text_widget.tag_config("current_match", background="#FF6B00", foreground="#FFFFFF")
        
        for idx, (start, end) in enumerate(self.matches):
            tag = "current_match" if idx == self.current_position else "search_highlight"
            self.text_widget.tag_add(tag, start, end)
            
        self.text_widget.configure(state="disabled")
        
    def goto_match(self, index):
        if not self.matches or index >= len(self.matches):
            return
            
        self.current_position = index
        start, end = self.matches[index]
        self.text_widget.see(start)
        self.highlight_matches()
        self.update_count_label()
        
        self.text_widget.configure(state="normal")
        self.text_widget.tag_remove("sel", "1.0", "end")
        self.text_widget.tag_add("sel", start, end)
        self.text_widget.configure(state="disabled")
        
    def search_next(self, event=None):
        if not self.matches:
            return
        next_pos = (self.current_position + 1) % len(self.matches)
        self.goto_match(next_pos)
        return "break"
        
    def search_prev(self, event=None):
        if not self.matches:
            return
        prev_pos = (self.current_position - 1) % len(self.matches)
        self.goto_match(prev_pos)
        return "break"
        
    def update_count_label(self):
        if self.matches:
            self.count_label.configure(text=f"{self.current_position + 1}/{len(self.matches)}")
        else:
            self.count_label.configure(text="0/0")
            
    def clear_highlights(self):
        self.text_widget.configure(state="normal")
        self.text_widget.tag_delete("search_highlight")
        self.text_widget.tag_delete("current_match")
        self.text_widget.configure(state="disabled")
