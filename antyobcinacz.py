"""
team_manager.py
Menadżer graficzny do tworzenia drużyn dla Football SIM
"""

import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser, ttk
from PIL import Image, ImageTk, ImageDraw, ImageColor
import os
import json
import random

class TeamManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Football SIM - Team Manager")
        self.root.geometry("1400x900")
        
        # Ścieżki
        self.sprites_dir = "sprites_output"
        
        # Dostępne moduły
        self.available_modules = {
            "shoes": [],
            "legs": [],
            "shorts": [],
            "jersey": [],
            "head": [],
            "hair": []
        }
        
        # Rozmiary ramek (zgodne z obcinaczem)
        self.module_frames = {
            "shoes": (100, 530, 135, 110),
            "legs": (85, 450, 160, 90),
            "shorts": (85, 300, 160, 170),
            "jersey": (48, 128, 224, 176),
            "head": (112, 32, 96, 104),
            "hair": (96, 16, 128, 80)
        }
        
        # Aktualna drużyna
        self.current_team = {
            "id": "BLUE",
            "name": "Blue Team",
            "color": "#3498db",
            "skin_color": "#fdbcb4",
            "players": []
        }
        
        # Załadowane zespoły
        self.teams = {}
        
        # Aktualnie wybrany zawodnik (1-11)
        self.selected_player = 1
        
        # Obrazki do wyświetlania
        self.player_photos = {}
        
        self.scan_modules()
        self.load_default_teams()
        self.create_ui()
        self.initialize_current_team()
        self.render_player(1)
    
    def scan_modules(self):
        """Skanuj dostępne moduły z folderów"""
        for module_type in self.available_modules.keys():
            module_path = os.path.join(self.sprites_dir, module_type)
            if os.path.exists(module_path):
                files = [f for f in os.listdir(module_path) if f.endswith('.png')]
                # Sortuj i dodaj
                self.available_modules[module_type] = sorted(files)
        
        # Debug info
        for mod, files in self.available_modules.items():
            print(f"{mod}: {len(files)} plików")
    
    def load_default_teams(self):
        """Załaduj domyślne drużyny"""
        self.teams["BLUE"] = {
            "id": "BLUE",
            "name": "Blue Team",
            "color": "#3498db",
            "skin_color": "#fdbcb4",
            "players": []
        }
        
        self.teams["BLACK"] = {
            "id": "BLACK",
            "name": "Black Team",
            "color": "#2c3e50",
            "skin_color": "#fdbcb4",
            "players": []
        }
    
    def initialize_current_team(self):
        """Inicjalizuj drużynę z pierwszymi elementami"""
        self.current_team["players"] = []
        
        for i in range(1, 12):
            player = {
                "number": i,
                "shoes": self.available_modules["shoes"][0] if self.available_modules["shoes"] else None,
                "legs": self.available_modules["legs"][0] if self.available_modules["legs"] else None,
                "shorts": self.available_modules["shorts"][0] if self.available_modules["shorts"] else None,
                "jersey": self.available_modules["jersey"][0] if self.available_modules["jersey"] else None,
                "head": self.available_modules["head"][0] if self.available_modules["head"] else None,
                "hair": self.available_modules["hair"][0] if self.available_modules["hair"] else None,
            }
            self.current_team["players"].append(player)
    
    def create_ui(self):
        # Panel górny - info o drużynie
        top_panel = tk.Frame(self.root, bg="#2c3e50", height=80)
        top_panel.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        top_panel.pack_propagate(False)
        
        # Nazwa drużyny
        tk.Label(top_panel, text="Drużyna:", bg="#2c3e50", fg="white",
                font=("Arial", 10)).grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.team_name_var = tk.StringVar(value=self.current_team["name"])
        team_entry = tk.Entry(top_panel, textvariable=self.team_name_var,
                             font=("Arial", 12, "bold"), width=20)
        team_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # ID drużyny
        tk.Label(top_panel, text="ID:", bg="#2c3e50", fg="white",
                font=("Arial", 10)).grid(row=0, column=2, padx=10, pady=5)
        
        self.team_id_var = tk.StringVar(value=self.current_team["id"])
        id_entry = tk.Entry(top_panel, textvariable=self.team_id_var,
                           font=("Arial", 12, "bold"), width=8)
        id_entry.grid(row=0, column=3, padx=5, pady=5)
        
        # Kolor drużyny
        tk.Label(top_panel, text="Kolor drużyny:", bg="#2c3e50", fg="white",
                font=("Arial", 10)).grid(row=0, column=4, padx=10, pady=5)
        
        self.team_color_btn = tk.Button(top_panel, text="   ", 
                                       bg=self.current_team["color"],
                                       command=self.choose_team_color,
                                       width=3, relief=tk.RAISED, bd=3)
        self.team_color_btn.grid(row=0, column=5, padx=5, pady=5)
        
        self.team_color_label = tk.Label(top_panel, text=self.current_team["color"],
                                         bg="#34495e", fg="white", font=("Arial", 9),
                                         width=10)
        self.team_color_label.grid(row=0, column=6, padx=5, pady=5)
        
        # Kolor skóry
        tk.Label(top_panel, text="Kolor skóry:", bg="#2c3e50", fg="white",
                font=("Arial", 10)).grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.skin_color_btn = tk.Button(top_panel, text="   ",
                                        bg=self.current_team["skin_color"],
                                        command=self.choose_skin_color,
                                        width=3, relief=tk.RAISED, bd=3)
        self.skin_color_btn.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        
        self.skin_color_label = tk.Label(top_panel, text=self.current_team["skin_color"],
                                         bg="#34495e", fg="white", font=("Arial", 9),
                                         width=10)
        self.skin_color_label.grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)
        
        # Przyciski akcji
        btn_random = tk.Button(top_panel, text="🎲 Losuj drużynę",
                              command=self.randomize_team, bg="#e67e22", fg="white",
                              font=("Arial", 10, "bold"))
        btn_random.grid(row=1, column=4, padx=5, pady=5)
        
        btn_save = tk.Button(top_panel, text="💾 Zapisz drużynę",
                            command=self.save_team, bg="#27ae60", fg="white",
                            font=("Arial", 10, "bold"))
        btn_save.grid(row=1, column=5, padx=5, pady=5)
        
        btn_load = tk.Button(top_panel, text="📁 Wczytaj drużynę",
                            command=self.load_team, bg="#3498db", fg="white",
                            font=("Arial", 10, "bold"))
        btn_load.grid(row=1, column=6, padx=5, pady=5)
        
        # Panel główny
        main_panel = tk.Frame(self.root, bg="#ecf0f1")
        main_panel.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Lewy panel - wybór zawodnika
        left_panel = tk.Frame(main_panel, bg="#34495e", width=200)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        tk.Label(left_panel, text="⚽ Zawodnicy", bg="#34495e", fg="white",
                font=("Arial", 12, "bold")).pack(pady=10)
        
        # Lista zawodników
        self.player_listbox = tk.Listbox(left_panel, bg="#2c3e50", fg="white",
                                        font=("Arial", 10), selectmode=tk.SINGLE,
                                        activestyle='none')
        self.player_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for i in range(1, 12):
            self.player_listbox.insert(tk.END, f"  Zawodnik #{i:02d}")
        
        self.player_listbox.selection_set(0)
        self.player_listbox.bind('<<ListboxSelect>>', self.on_player_select)
        
        # Środkowy panel - podgląd zawodnika
        center_panel = tk.Frame(main_panel, bg="#2c3e50")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(center_panel, text="👤 Podgląd zawodnika", bg="#2c3e50", fg="white",
                font=("Arial", 12, "bold")).pack(pady=10)
        
        self.player_canvas = tk.Canvas(center_panel, bg="#1a1a1a", 
                                      width=350, height=700, highlightthickness=0)
        self.player_canvas.pack(pady=10)
        
        # Prawy panel - wybór modułów
        right_panel = tk.Frame(main_panel, bg="#34495e", width=400)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        tk.Label(right_panel, text="🎨 Moduły zawodnika", bg="#34495e", fg="white",
                font=("Arial", 12, "bold")).pack(pady=10)
        
        # Scrollable frame dla modułów
        canvas_scroll = tk.Canvas(right_panel, bg="#34495e", highlightthickness=0)
        scrollbar = tk.Scrollbar(right_panel, orient="vertical", command=canvas_scroll.yview)
        modules_frame = tk.Frame(canvas_scroll, bg="#34495e")
        
        modules_frame.bind(
            "<Configure>",
            lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
        )
        
        canvas_scroll.create_window((0, 0), window=modules_frame, anchor="nw")
        canvas_scroll.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Tworzenie selektorów dla każdego modułu
        self.module_vars = {}
        module_labels = {
            "shoes": "👟 Buty",
            "legs": "🦵 Nogi",
            "shorts": "🩳 Spodenki",
            "jersey": "👕 Koszulka",
            "head": "😀 Głowa",
            "hair": "💇 Włosy"
        }
        
        for module, label in module_labels.items():
            frame = tk.Frame(modules_frame, bg="#2c3e50", relief=tk.RAISED, bd=2)
            frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(frame, text=label, bg="#2c3e50", fg="white",
                    font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=5, pady=5)
            
            self.module_vars[module] = tk.StringVar()
            
            if self.available_modules[module]:
                combo = ttk.Combobox(frame, textvariable=self.module_vars[module],
                                    values=self.available_modules[module],
                                    state="readonly", width=30)
                combo.pack(padx=5, pady=5, fill=tk.X)
                combo.current(0)
                combo.bind('<<ComboboxSelected>>', 
                          lambda e, m=module: self.on_module_change(m))
            else:
                tk.Label(frame, text="Brak dostępnych elementów", 
                        bg="#2c3e50", fg="#e74c3c",
                        font=("Arial", 9, "italic")).pack(padx=5, pady=5)
    
    def choose_team_color(self):
        """Wybierz kolor drużyny"""
        color = colorchooser.askcolor(initialcolor=self.current_team["color"])
        if color[1]:
            self.current_team["color"] = color[1]
            self.team_color_btn.config(bg=color[1])
            self.team_color_label.config(text=color[1])
            self.render_player(self.selected_player)
    
    def choose_skin_color(self):
        """Wybierz kolor skóry"""
        color = colorchooser.askcolor(initialcolor=self.current_team["skin_color"])
        if color[1]:
            self.current_team["skin_color"] = color[1]
            self.skin_color_btn.config(bg=color[1])
            self.skin_color_label.config(text=color[1])
            self.render_player(self.selected_player)
    
    def on_player_select(self, event):
        """Wybór zawodnika z listy"""
        selection = self.player_listbox.curselection()
        if selection:
            self.selected_player = selection[0] + 1
            self.load_player_to_ui(self.selected_player)
            self.render_player(self.selected_player)
    
    def load_player_to_ui(self, player_num):
        """Załaduj dane zawodnika do UI"""
        player = self.current_team["players"][player_num - 1]
        
        for module in self.module_vars.keys():
            if player[module] and player[module] in self.available_modules[module]:
                idx = self.available_modules[module].index(player[module])
                self.module_vars[module].set(player[module])
    
    def on_module_change(self, module):
        """Zmiana modułu zawodnika"""
        player = self.current_team["players"][self.selected_player - 1]
        player[module] = self.module_vars[module].get()
        self.render_player(self.selected_player)
    
    def render_player(self, player_num):
        """Renderuj zawodnika na canvas"""
        self.player_canvas.delete("all")
        
        player = self.current_team["players"][player_num - 1]
        
        # Stwórz sprite 320x640
        composite = Image.new('RGBA', (320, 640), (0, 0, 0, 0))
        
        # Kolejność renderowania (z-order)
        render_order = ["shoes", "legs", "shorts", "jersey", "head", "hair"]
        
        for module in render_order:
            if not player[module]:
                continue
            
            module_path = os.path.join(self.sprites_dir, module, player[module])
            
            if not os.path.exists(module_path):
                continue
            
            try:
                img = Image.open(module_path).convert('RGBA')
                
                # Kolorowanie
                if module in ["shorts", "jersey"]:
                    img = self.colorize_image(img, self.current_team["color"])
                elif module in ["legs", "head"]:
                    img = self.colorize_image(img, self.current_team["skin_color"])
                
                # Pozycja z ramki
                frame = self.module_frames[module]
                x, y = frame[0], frame[1]
                
                composite.paste(img, (x, y), img)
                
            except Exception as e:
                print(f"Błąd ładowania {module}: {e}")
        
        # Dodaj numer zawodnika na koszulce
        from PIL import ImageFont, ImageDraw
        draw = ImageDraw.Draw(composite)
        try:
            # Spróbuj załadować font (może nie działać wszędzie)
            font = ImageFont.truetype("arial.ttf", 40)
        except:
            font = ImageFont.load_default()
        
        # Numer na środku koszulki
        number_text = str(player_num)
        # Pozycja: środek koszulki
        jersey_frame = self.module_frames["jersey"]
        text_x = jersey_frame[0] + jersey_frame[2] // 2
        text_y = jersey_frame[1] + jersey_frame[3] // 2
        
        # Cień
        draw.text((text_x+2, text_y+2), number_text, fill="black", 
                 font=font, anchor="mm")
        # Numer
        draw.text((text_x, text_y), number_text, fill="white", 
                 font=font, anchor="mm")
        
        # Przeskaluj do wyświetlenia
        display_img = composite.resize((160, 320), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(display_img)
        self.player_photos[player_num] = photo
        
        # Wyświetl
        self.player_canvas.create_image(175, 350, image=photo, anchor=tk.CENTER)
        
        # Info
        self.player_canvas.create_text(175, 50, 
                                       text=f"Zawodnik #{player_num:02d}",
                                       fill="white", font=("Arial", 16, "bold"))
    
    def colorize_image(self, img, hex_color):
        """Koloruj białe/szare obszary obrazka na dany kolor"""
        img = img.convert('RGBA')
        data = img.getdata()
        
        target_color = ImageColor.getrgb(hex_color)
        
        new_data = []
        for item in data:
            # Jeśli piksel jest jasny (biały/szary) i nieprzezroczysty
            if item[3] > 0:  # Alpha > 0
                # Średnia RGB (jasność)
                brightness = (item[0] + item[1] + item[2]) / 3
                
                # Jeśli jasny (>128), koloruj
                if brightness > 128:
                    # Zachowaj jasność, ale zmień kolor
                    factor = brightness / 255.0
                    new_data.append((
                        int(target_color[0] * factor),
                        int(target_color[1] * factor),
                        int(target_color[2] * factor),
                        item[3]
                    ))
                else:
                    # Ciemne piksele zostaw (kontury)
                    new_data.append(item)
            else:
                new_data.append(item)
        
        img.putdata(new_data)
        return img
    
    def randomize_team(self):
        """Losuj moduły dla całej drużyny (k5)"""
        if not messagebox.askyesno("Losowanie", 
                                   "Wylosować losowe moduły dla wszystkich zawodników?\n(k5 dla każdego modułu)"):
            return
        
        for player in self.current_team["players"]:
            for module in ["shoes", "legs", "shorts", "jersey", "head", "hair"]:
                available = self.available_modules[module]
                if available:
                    # k5 = losuj od 0 do 4 (pierwsze 5 elementów)
                    max_idx = min(4, len(available) - 1)
                    idx = random.randint(0, max_idx)
                    player[module] = available[idx]
        
        # Odśwież UI
        self.load_player_to_ui(self.selected_player)
        self.render_player(self.selected_player)
        
        messagebox.showinfo("Sukces", "Drużyna wylosowana! 🎲")
    
    def save_team(self):
        """Zapisz drużynę do pliku JSON"""
        self.current_team["name"] = self.team_name_var.get()
        self.current_team["id"] = self.team_id_var.get()
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")],
            initialfile=f"{self.current_team['id']}.json"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.current_team, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Sukces", f"Drużyna zapisana:\n{filename}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można zapisać:\n{e}")
    
    def load_team(self):
        """Wczytaj drużynę z pliku JSON"""
        filename = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json"), ("All", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    self.current_team = json.load(f)
                
                # Odśwież UI
                self.team_name_var.set(self.current_team["name"])
                self.team_id_var.set(self.current_team["id"])
                self.team_color_btn.config(bg=self.current_team["color"])
                self.team_color_label.config(text=self.current_team["color"])
                self.skin_color_btn.config(bg=self.current_team["skin_color"])
                self.skin_color_label.config(text=self.current_team["skin_color"])
                
                self.load_player_to_ui(self.selected_player)
                self.render_player(self.selected_player)
                
                messagebox.showinfo("Sukces", f"Wczytano drużynę: {self.current_team['name']}")
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie można wczytać:\n{e}")


def main():
    root = tk.Tk()
    app = TeamManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()