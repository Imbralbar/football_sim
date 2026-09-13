"""
sprite_template_cutter.py
Narzędzie do wycinania modułów z FIXED ramkami - dopasowujesz obrazek do ramki
+ Podgląd złożonej postaci + Grid + Eksport wszystkich
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk, ImageDraw
import os

class SpriteTemplateCutter:
    def __init__(self, root):
        self.root = root
        self.root.title("Football SIM - Template-Based Sprite Cutter")
        self.root.geometry("1600x900")
        
        # Konfiguracja ramek (x, y, width, height) dla sprite'a 400x800px (2x większy)
        self.templates = {
            "shoes": {
                "name": "Buty",
                "frame": (100, 530, 135, 110),  # 2x większy
                "color": "#e74c3c",
                "fill_color": "#8B0000",
                "z_order": 1
            },
            "legs": {
                "name": "Nogi (kolano→pas)",
                "frame": (85, 450, 160, 90),  # 2x większy
                "color": "#f39c12",
                "fill_color": "#8B4500",
                "z_order": 2
            },
            "shorts": {
                "name": "Spodenki",
                "frame": (85, 300, 160, 170),  # 2x większy
                "color": "#3498db",
                "fill_color": "#00008B",
                "z_order": 3
            },
            "jersey": {
                "name": "Koszulka z rękawami",
                "frame": (48, 128, 224, 176),  # 2x większy
                "color": "#2ecc71",
                "fill_color": "#006400",
                "z_order": 4
            },
            "head": {
                "name": "Głowa (łysa)",
                "frame": (112, 32, 96, 104),  # 2x większy
                "color": "#9b59b6",
                "fill_color": "#4B0082",
                "z_order": 5
            },
            "hair": {
                "name": "Fryzura (overlay)",
                "frame": (96, 16, 128, 80),  # 2x większy
                "color": "#e67e22",
                "fill_color": "#8B4000",
                "z_order": 6
            }
        }
        
        # Stan obrazka
        self.current_images = {}
        self.display_images = {}
        self.image_positions = {}
        self.image_scales = {}
        self.saved_modules = {}
        
        # Inicjalizuj pozycje i skale
        for module in self.templates.keys():
            self.image_positions[module] = (0, 0)
            self.image_scales[module] = 1.0
        
        self.current_module = "shoes"
        self.drag_start = None
        
        # Ustawienia UI
        self.show_grid = tk.BooleanVar(value=False)
        self.grid_size = tk.IntVar(value=16)  # 2x większy grid
        self.scale_var = tk.DoubleVar(value=100.0)  # Slider skali
        
        self.output_dir = "sprites_output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.create_ui()
    
    def create_ui(self):
        # Panel lewy z scrollbarem - kontrolki
        left_outer = tk.Frame(self.root, bg="#2c3e50", width=300)
        left_outer.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_outer.pack_propagate(False)
        
        # Canvas dla scrollowania
        left_canvas = tk.Canvas(left_outer, bg="#2c3e50", highlightthickness=0)
        scrollbar = tk.Scrollbar(left_outer, orient="vertical", command=left_canvas.yview)
        
        # Frame wewnętrzny (scrollowany)
        left_panel = tk.Frame(left_canvas, bg="#2c3e50")
        
        # Konfiguracja scrollowania
        left_panel.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )
        
        left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
        left_canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pakowanie scrollbar i canvas
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Bindowanie scroll myszką
        def _on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # === ZAWARTOŚĆ LEWEGO PANELU ===
        
        # Tytuł
        tk.Label(left_panel, text="🔧 Kontrolki", bg="#2c3e50", fg="white",
                font=("Arial", 14, "bold")).pack(pady=10)
        
        tk.Frame(left_panel, bg="#34495e", height=2).pack(fill=tk.X, padx=10, pady=5)
        
        # Ładowanie wszystkich modułów
        tk.Label(left_panel, text="📁 Wczytaj obrazki:", 
                bg="#2c3e50", fg="#ecf0f1", font=("Arial", 10, "bold")).pack(pady=(10,5))
        
        load_all_btn = tk.Button(left_panel, text="Wczytaj wszystkie (6 plików)",
                                command=self.load_all_modules, bg="#3498db", fg="white",
                                font=("Arial", 9, "bold"), wraplength=250)
        load_all_btn.pack(padx=10, pady=5, fill=tk.X)
        
        tk.Label(left_panel, text="lub pojedynczo:", 
                bg="#2c3e50", fg="#95a5a6", font=("Arial", 8)).pack()
        
        # Przyciski ładowania dla każdego modułu
        for module, config in self.templates.items():
            btn_frame = tk.Frame(left_panel, bg="#2c3e50")
            btn_frame.pack(fill=tk.X, padx=10, pady=2)
            
            color_box = tk.Label(btn_frame, bg=config["color"], width=2)
            color_box.pack(side=tk.LEFT, padx=(0,5))
            
            btn = tk.Button(btn_frame, text=f"📄 {config['name']}", 
                          command=lambda m=module: self.load_single_module(m),
                          bg="#34495e", fg="white", font=("Arial", 8), anchor="w")
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Frame(left_panel, bg="#34495e", height=2).pack(fill=tk.X, padx=10, pady=10)
        
        # Wybór aktywnego modułu
        tk.Label(left_panel, text="🎯 Aktywny moduł:", 
                bg="#2c3e50", fg="#ecf0f1", font=("Arial", 10, "bold")).pack(pady=(5,5))
        
        self.module_var = tk.StringVar(value="shoes")
        
        for module, config in self.templates.items():
            rb = tk.Radiobutton(left_panel, text=config["name"], 
                              variable=self.module_var, value=module,
                              command=self.on_module_select, bg="#2c3e50", 
                              fg="white", selectcolor="#34495e",
                              font=("Arial", 9), activebackground="#2c3e50",
                              activeforeground="white")
            rb.pack(anchor=tk.W, padx=20, pady=2)
        
        tk.Frame(left_panel, bg="#34495e", height=2).pack(fill=tk.X, padx=10, pady=10)
        
        # Kontrolki transformacji
        tk.Label(left_panel, text="🎨 Transformacje:", 
                bg="#2c3e50", fg="#ecf0f1", font=("Arial", 10, "bold")).pack(pady=(5,5))
        
        # Skala - SLIDER
        scale_frame = tk.Frame(left_panel, bg="#2c3e50")
        scale_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(scale_frame, text="Skala:", bg="#2c3e50", fg="white",
                font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(0,2))
        
        # Slider frame
        slider_frame = tk.Frame(scale_frame, bg="#2c3e50")
        slider_frame.pack(fill=tk.X)
        
        self.scale_slider = tk.Scale(slider_frame, from_=10, to=500, 
                                     orient=tk.HORIZONTAL,
                                     variable=self.scale_var,
                                     command=self.on_scale_slider_change,
                                     bg="#34495e", fg="white",
                                     highlightthickness=0,
                                     troughcolor="#1a1a1a",
                                     activebackground="#3498db",
                                     resolution=1,  # Krok co 1%
                                     length=220)
        self.scale_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.scale_label = tk.Label(slider_frame, text="100%", bg="#27ae60", fg="white",
                                   font=("Arial", 9, "bold"), width=6, relief=tk.RAISED)
        self.scale_label.pack(side=tk.LEFT, padx=(5,0))
        
        # Przyciski fine-tune
        fine_frame = tk.Frame(left_panel, bg="#2c3e50")
        fine_frame.pack(fill=tk.X, padx=10, pady=2)
        
        btn_minus_10 = tk.Button(fine_frame, text="--10%", 
                               command=lambda: self.adjust_scale_value(-10),
                               bg="#c0392b", fg="white", font=("Arial", 8), width=6)
        btn_minus_10.pack(side=tk.LEFT, padx=2)
        
        btn_minus_1 = tk.Button(fine_frame, text="-1%", 
                              command=lambda: self.adjust_scale_value(-1),
                              bg="#e74c3c", fg="white", font=("Arial", 8), width=5)
        btn_minus_1.pack(side=tk.LEFT, padx=2)
        
        btn_plus_1 = tk.Button(fine_frame, text="+1%", 
                             command=lambda: self.adjust_scale_value(1),
                             bg="#27ae60", fg="white", font=("Arial", 8), width=5)
        btn_plus_1.pack(side=tk.LEFT, padx=2)
        
        btn_plus_10 = tk.Button(fine_frame, text="++10%", 
                              command=lambda: self.adjust_scale_value(10),
                              bg="#229954", fg="white", font=("Arial", 8), width=6)
        btn_plus_10.pack(side=tk.LEFT, padx=2)
        
        # Reset
        reset_btn = tk.Button(left_panel, text="🔄 Resetuj pozycję i skalę",
                            command=self.reset_transform, bg="#95a5a6", fg="white",
                            font=("Arial", 9))
        reset_btn.pack(padx=10, pady=5, fill=tk.X)
        
        # Grid
        grid_frame = tk.Frame(left_panel, bg="#2c3e50")
        grid_frame.pack(fill=tk.X, padx=10, pady=5)
        
        grid_cb = tk.Checkbutton(grid_frame, text="Pokaż siatkę", 
                                variable=self.show_grid, command=self.redraw_canvas,
                                bg="#2c3e50", fg="white", selectcolor="#34495e",
                                activebackground="#2c3e50", activeforeground="white")
        grid_cb.pack(side=tk.LEFT)
        
        grid_spin = tk.Spinbox(grid_frame, from_=5, to=100, increment=5,
                              textvariable=self.grid_size, width=5,
                              command=self.redraw_canvas, bg="#34495e", fg="white")
        grid_spin.pack(side=tk.LEFT, padx=5)
        
        tk.Label(grid_frame, text="px", bg="#2c3e50", fg="white").pack(side=tk.LEFT)
        
        # Info
        tk.Label(left_panel, text="💡 Przeciągaj obrazek myszką", 
                bg="#2c3e50", fg="#95a5a6", font=("Arial", 8, "italic")).pack(pady=5)
        
        tk.Frame(left_panel, bg="#34495e", height=2).pack(fill=tk.X, padx=10, pady=10)
        
        # Przyciski zapisu
        tk.Label(left_panel, text="💾 Zapis modułów:", 
                bg="#2c3e50", fg="#ecf0f1", font=("Arial", 10, "bold")).pack(pady=(5,5))
        
        for module, config in self.templates.items():
            btn_frame = tk.Frame(left_panel, bg="#2c3e50")
            btn_frame.pack(fill=tk.X, padx=10, pady=2)
            
            color_box = tk.Label(btn_frame, bg=config["color"], width=2)
            color_box.pack(side=tk.LEFT, padx=(0,5))
            
            btn = tk.Button(btn_frame, text=f"💾 {config['name']}", 
                          command=lambda m=module: self.save_module(m),
                          bg="#27ae60", fg="white", font=("Arial", 8, "bold"), anchor="w")
            btn.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Eksport wszystkich
        tk.Frame(left_panel, bg="#34495e", height=2).pack(fill=tk.X, padx=10, pady=5)
        
        export_all_btn = tk.Button(left_panel, text="📦 Eksportuj WSZYSTKIE moduły",
                                  command=self.export_all_modules, bg="#8e44ad", fg="white",
                                  font=("Arial", 10, "bold"), wraplength=250)
        export_all_btn.pack(padx=10, pady=10, fill=tk.X)
        
        # Padding na dole dla scrollowania
        tk.Label(left_panel, text="", bg="#2c3e50", height=2).pack()
        
        # === GŁÓWNY KONTENER ===
        
        main_container = tk.Frame(self.root, bg="#ecf0f1")
        main_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas główny (edycja)
        canvas_container = tk.Frame(main_container, bg="#ecf0f1")
        canvas_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Info górny
        info_frame = tk.Frame(canvas_container, bg="#34495e", height=40)
        info_frame.pack(side=tk.TOP, fill=tk.X)
        info_frame.pack_propagate(False)
        
        self.info_label = tk.Label(info_frame, 
                                   text="Wczytaj obrazki, wybierz moduł i dopasuj obrazek do ramki (kolorowy prostokąt)",
                                   bg="#34495e", fg="white", font=("Arial", 10))
        self.info_label.pack(expand=True)
        
        # Canvas edycji
        self.canvas = tk.Canvas(canvas_container, bg="#1a1a1a", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bindingi
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        
        # Panel podglądu (po prawej)
        preview_container = tk.Frame(main_container, bg="#2c3e50", width=280)
        preview_container.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        preview_container.pack_propagate(False)
        
        tk.Label(preview_container, text="👤 Podgląd postaci", 
                bg="#2c3e50", fg="white", font=("Arial", 12, "bold")).pack(pady=10)
        
        tk.Frame(preview_container, bg="#34495e", height=2).pack(fill=tk.X, padx=10, pady=5)
        
        # Canvas podglądu (2x większy)
        self.preview_canvas = tk.Canvas(preview_container, bg="#1a1a1a", 
                                       width=180, height=360, highlightthickness=0)
        self.preview_canvas.pack(padx=10, pady=10)
        
        # Przycisk odświeżenia
        refresh_preview_btn = tk.Button(preview_container, text="🔄 Odśwież podgląd",
                                       command=self.update_preview, bg="#3498db", fg="white",
                                       font=("Arial", 9))
        refresh_preview_btn.pack(padx=10, pady=5, fill=tk.X)
        
        # Info o podglądzie
        tk.Label(preview_container, 
                text="Pokazuje złożoną postać\nz zapisanych modułów\n(400×800px)",
                bg="#2c3e50", fg="#95a5a6", font=("Arial", 8), justify=tk.CENTER).pack(pady=5)
        
        # Panel dolny - historia
        bottom_frame = tk.Frame(canvas_container, bg="#2c3e50", height=100)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_frame.pack_propagate(False)
        
        tk.Label(bottom_frame, text="📋 Historia zapisów:", 
                bg="#2c3e50", fg="white", font=("Arial", 9, "bold")).pack(anchor=tk.W, padx=10, pady=2)
        
        self.history_text = tk.Text(bottom_frame, height=4, bg="#1a1a1a", fg="#2ecc71",
                                   font=("Courier", 8), wrap=tk.WORD)
        self.history_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))
        
        # Rysuj początkowo
        self.redraw_canvas()
        self.update_preview()
    
    def load_all_modules(self):
        """Wczytaj 6 plików naraz w kolejności"""
        messagebox.showinfo("Wczytywanie", 
                          "Wybierz 6 plików w kolejności:\n\n" +
                          "1. Buty\n2. Nogi\n3. Spodenki\n4. Koszulka\n5. Głowa\n6. Włosy")
        
        modules_order = ["shoes", "legs", "shorts", "jersey", "head", "hair"]
        
        for module in modules_order:
            file_path = filedialog.askopenfilename(
                title=f"Wybierz obrazek dla: {self.templates[module]['name']}",
                filetypes=[("Obrazki", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Wszystkie", "*.*")]
            )
            
            if file_path:
                self.load_image_for_module(module, file_path)
            else:
                response = messagebox.askyesno("Pomiń?", 
                    f"Nie wybrano pliku dla '{self.templates[module]['name']}'.\nPominąć i kontynuować?")
                if not response:
                    break
        
        self.redraw_canvas()
    
    def load_single_module(self, module):
        """Wczytaj obrazek dla pojedynczego modułu"""
        file_path = filedialog.askopenfilename(
            title=f"Wybierz obrazek dla: {self.templates[module]['name']}",
            filetypes=[("Obrazki", "*.png *.jpg *.jpeg *.gif *.bmp"), ("Wszystkie", "*.*")]
        )
        
        if file_path:
            self.load_image_for_module(module, file_path)
            self.redraw_canvas()
    
    def load_image_for_module(self, module, file_path):
        """Wczytaj i zapisz obrazek dla modułu"""
        try:
            img = Image.open(file_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            self.current_images[module] = img
            self.image_positions[module] = (0, 0)
            self.image_scales[module] = 1.0
            self.scale_var.set(100.0)
            
            self.info_label.config(text=f"✓ Wczytano: {self.templates[module]['name']} - {os.path.basename(file_path)}")
            
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można wczytać obrazka dla {module}:\n{str(e)}")
    
    def on_module_select(self):
        """Zmiana aktywnego modułu"""
        self.current_module = self.module_var.get()
        scale = self.image_scales.get(self.current_module, 1.0)
        self.scale_var.set(scale * 100)
        self.scale_label.config(text=f"{int(scale*100)}%")
        self.redraw_canvas()
    
    def on_scale_slider_change(self, value):
        """Zmiana slidera skali"""
        if self.current_module not in self.current_images:
            return
        
        scale_percent = float(value)
        self.image_scales[self.current_module] = scale_percent / 100.0
        self.scale_label.config(text=f"{int(scale_percent)}%")
        self.redraw_canvas()
    
    def adjust_scale_value(self, delta_percent):
        """Dostosuj skalę o delta procent"""
        if self.current_module not in self.current_images:
            messagebox.showwarning("Uwaga", f"Nie wczytano obrazka dla '{self.templates[self.current_module]['name']}'")
            return
        
        current = self.scale_var.get()
        new_value = max(10, min(500, current + delta_percent))
        self.scale_var.set(new_value)
        self.on_scale_slider_change(new_value)
    
    def reset_transform(self):
        """Resetuj transformacje aktywnego modułu"""
        self.image_positions[self.current_module] = (0, 0)
        self.image_scales[self.current_module] = 1.0
        self.scale_var.set(100.0)
        self.scale_label.config(text="100%")
        self.redraw_canvas()
    
    def draw_grid(self, canvas, width, height, offset_x, offset_y):
        """Rysuj siatkę pomocniczą"""
        if not self.show_grid.get():
            return
        
        grid_size = self.grid_size.get()
        
        # Linie pionowe
        for x in range(0, 320, grid_size):
            canvas.create_line(
                offset_x + x, offset_y,
                offset_x + x, offset_y + 640,
                fill="#333333", dash=(2, 2), tags="grid"
            )
        
        # Linie poziome
        for y in range(0, 640, grid_size):
            canvas.create_line(
                offset_x, offset_y + y,
                offset_x + 320, offset_y + y,
                fill="#333333", dash=(2, 2), tags="grid"
            )
        
        # Ramka główna
        canvas.create_rectangle(
            offset_x, offset_y,
            offset_x + 320, offset_y + 640,
            outline="#555555", width=2, tags="grid"
        )
    
    def redraw_canvas(self):
        """Przerysuj cały canvas"""
        self.canvas.delete("all")
        
        canvas_width = self.canvas.winfo_width() if self.canvas.winfo_width() > 1 else 800
        canvas_height = self.canvas.winfo_height() if self.canvas.winfo_height() > 1 else 600
        
        # Offset dla centrowania (400x800px sprite)
        offset_x = canvas_width // 2 - 160
        offset_y = canvas_height // 2 - 280
        
        # Rysuj siatkę
        self.draw_grid(self.canvas, canvas_width, canvas_height, offset_x, offset_y)
        
        # Rysuj wszystkie ramki i obrazki
        for module, config in self.templates.items():
            frame = config["frame"]
            x, y, w, h = frame
            
            # Ramka
            is_active = (module == self.current_module)
            outline_width = 3 if is_active else 1
            outline_color = config["color"] if is_active else "#555555"
            fill_color = config["fill_color"] if is_active else ""
            
            self.canvas.create_rectangle(
                offset_x + x, offset_y + y,
                offset_x + x + w, offset_y + y + h,
                outline=outline_color, width=outline_width,
                fill=fill_color, stipple="gray25" if is_active else "",
                tags=f"frame_{module}"
            )
            
            # Label
            self.canvas.create_text(
                offset_x + x + w//2, offset_y + y - 12,
                text=config["name"], fill=config["color"],
                font=("Arial", 9 if not is_active else 11, "bold" if is_active else "normal"),
                tags=f"label_{module}"
            )
            
            # Obrazek (jeśli wczytany)
            if module in self.current_images:
                img = self.current_images[module]
                scale = self.image_scales[module]
                pos = self.image_positions[module]
                
                # Skaluj obrazek
                new_size = (int(img.width * scale), int(img.height * scale))
                scaled_img = img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Konwertuj do PhotoImage
                photo = ImageTk.PhotoImage(scaled_img)
                self.display_images[module] = photo  # Zachowaj referencję
                
                # Rysuj obrazek z przesunięciem
                img_x = offset_x + x + w//2 + pos[0]
                img_y = offset_y + y + h//2 + pos[1]
                
                self.canvas.create_image(img_x, img_y, image=photo, 
                                       tags=f"image_{module}", anchor=tk.CENTER)
                
                # Przenieś obrazek pod ramkę
                self.canvas.tag_lower(f"image_{module}", f"frame_{module}")
    
    def on_mouse_down(self, event):
        """Start przeciągania"""
        if self.current_module not in self.current_images:
            return
        self.drag_start = (event.x, event.y)
    
    def on_mouse_drag(self, event):
        """Przeciąganie obrazka"""
        if self.drag_start is None or self.current_module not in self.current_images:
            return
        
        dx = event.x - self.drag_start[0]
        dy = event.y - self.drag_start[1]
        
        old_pos = self.image_positions[self.current_module]
        self.image_positions[self.current_module] = (old_pos[0] + dx, old_pos[1] + dy)
        
        self.drag_start = (event.x, event.y)
        self.redraw_canvas()
    
    def on_mouse_up(self, event):
        """Koniec przeciągania"""
        self.drag_start = None
    
    def save_module(self, module):
        """Zapisz wycięty moduł"""
        if module not in self.current_images:
            messagebox.showwarning("Uwaga", f"Nie wczytano obrazka dla '{self.templates[module]['name']}'")
            return
        
        # Pytaj o nazwę
        module_name = simpledialog.askstring(
            "Nazwa modułu",
            f"Podaj nazwę dla: {self.templates[module]['name']}",
            initialvalue=f"{module}_01"
        )
        
        if not module_name:
            return
        
        # Sanityzuj
        module_name = "".join(c for c in module_name if c.isalnum() or c in "_-")
        
        try:
            # Pobierz konfigurację
            img = self.current_images[module]
            scale = self.image_scales[module]
            pos = self.image_positions[module]
            frame = self.templates[module]["frame"]
            frame_w, frame_h = frame[2], frame[3]
            
            # Przeskaluj obrazek
            scaled_img = img.resize(
                (int(img.width * scale), int(img.height * scale)),
                Image.Resampling.LANCZOS
            )
            
            # Stwórz płótno o rozmiarze ramki
            output = Image.new('RGBA', (frame_w, frame_h), (0, 0, 0, 0))
            
            # Oblicz pozycję wklejenia (center obrazka = center ramki + offset)
            paste_x = frame_w // 2 - scaled_img.width // 2 + pos[0]
            paste_y = frame_h // 2 - scaled_img.height // 2 + pos[1]
            
            # Wklej obrazek
            output.paste(scaled_img, (paste_x, paste_y), scaled_img)
            
            # Zapisz w pamięci (do podglądu)
            self.saved_modules[module] = output
            
            # Zapisz
            module_folder = os.path.join(self.output_dir, module)
            os.makedirs(module_folder, exist_ok=True)
            
            output_path = os.path.join(module_folder, f"{module_name}.png")
            output.save(output_path, "PNG")
            
            # Historia
            self.history_text.insert(tk.END, 
                f"✓ {self.templates[module]['name']}: {module_name}.png [{frame_w}×{frame_h}]\n")
            self.history_text.see(tk.END)
            
            # Odśwież podgląd
            self.update_preview()
            
            messagebox.showinfo("Sukces", f"Moduł zapisany:\n{output_path}")
            
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można zapisać modułu:\n{str(e)}")
    
    def export_all_modules(self):
        """Eksportuj wszystkie moduły naraz"""
        if not self.current_images:
            messagebox.showwarning("Uwaga", "Nie wczytano żadnych obrazków!")
            return
        
        # Pytaj o prefix nazwy
        prefix = simpledialog.askstring(
            "Eksport wszystkich",
            "Podaj prefix nazwy dla wszystkich modułów\n(np. 'player1', 'team_blue'):",
            initialvalue="sprite"
        )
        
        if not prefix:
            return
        
        prefix = "".join(c for c in prefix if c.isalnum() or c in "_-")
        
        saved_count = 0
        errors = []
        
        for module in self.templates.keys():
            if module not in self.current_images:
                continue
            
            try:
                # Pobierz konfigurację
                img = self.current_images[module]
                scale = self.image_scales[module]
                pos = self.image_positions[module]
                frame = self.templates[module]["frame"]
                frame_w, frame_h = frame[2], frame[3]
                
                # Przeskaluj obrazek
                scaled_img = img.resize(
                    (int(img.width * scale), int(img.height * scale)),
                    Image.Resampling.LANCZOS
                )
                
                # Stwórz płótno o rozmiarze ramki
                output = Image.new('RGBA', (frame_w, frame_h), (0, 0, 0, 0))
                
                # Oblicz pozycję wklejenia
                paste_x = frame_w // 2 - scaled_img.width // 2 + pos[0]
                paste_y = frame_h // 2 - scaled_img.height // 2 + pos[1]
                
                # Wklej obrazek
                output.paste(scaled_img, (paste_x, paste_y), scaled_img)
                
                # Zapisz w pamięci
                self.saved_modules[module] = output
                
                # Zapisz do pliku
                module_folder = os.path.join(self.output_dir, module)
                os.makedirs(module_folder, exist_ok=True)
                
                output_path = os.path.join(module_folder, f"{prefix}_{module}.png")
                output.save(output_path, "PNG")
                
                saved_count += 1
                
                # Historia
                self.history_text.insert(tk.END, 
                    f"✓ {self.templates[module]['name']}: {prefix}_{module}.png\n")
                
            except Exception as e:
                errors.append(f"{module}: {str(e)}")
        
        self.history_text.see(tk.END)
        
        # Odśwież podgląd
        self.update_preview()
        
        # Podsumowanie
        if errors:
            messagebox.showwarning("Eksport zakończony z błędami", 
                f"Zapisano: {saved_count} modułów\n\nBłędy:\n" + "\n".join(errors))
        else:
            messagebox.showinfo("Sukces", 
                f"Pomyślnie wyeksportowano {saved_count} modułów!\n\n" +
                f"Folder: {self.output_dir}\nPrefix: {prefix}_")
    
    def update_preview(self):
        """Aktualizuj podgląd złożonej postaci"""
        self.preview_canvas.delete("all")
        
        if not self.saved_modules:
            self.preview_canvas.create_text(
                110, 240, text="Brak zapisanych\nmodułów",
                fill="#555555", font=("Arial", 10), justify=tk.CENTER
            )
            return
        
        # Stwórz złożony obrazek (320x640px)
        composite = Image.new('RGBA', (320, 640), (0, 0, 0, 0))
        
        # Sortuj moduły według z_order
        sorted_modules = sorted(self.templates.items(), key=lambda x: x[1]['z_order'])
        
        for module, config in sorted_modules:
            if module in self.saved_modules:
                frame = config["frame"]
                x, y = frame[0], frame[1]
                
                # Wklej moduł
                composite.paste(self.saved_modules[module], (x, y), self.saved_modules[module])
        
        # Przeskaluj do podglądu (160x320 - połowa rozmiaru dla wyświetlenia)
        preview_scaled = composite.resize((160, 320), Image.Resampling.LANCZOS)
        preview_img = ImageTk.PhotoImage(preview_scaled)
        self.preview_photo = preview_img  # Zachowaj referencję
        
        # Wyświetl
        self.preview_canvas.create_image(90, 180, image=preview_img, anchor=tk.CENTER)
        
        # Ramka
        self.preview_canvas.create_rectangle(10, 20, 170, 340, outline="#555555", width=1)
        
        # Info
        count = len(self.saved_modules)
        self.preview_canvas.create_text(
            90, 10, text=f"Zapisane: {count}/6",
            fill="#2ecc71" if count == 6 else "#f39c12", 
            font=("Arial", 10, "bold")
        )
        
        # Rozmiar
        self.preview_canvas.create_text(
            90, 355, text="400×800px",
            fill="#95a5a6", font=("Arial", 8)
        )


def main():
    root = tk.Tk()
    app = SpriteTemplateCutter(root)
    root.mainloop()


if __name__ == "__main__":
    main()