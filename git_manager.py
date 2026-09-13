import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

class GitManager:
    def __init__(self, repo_path):
        self.repo_path = Path(repo_path)
        if not self.repo_path.exists():
            raise FileNotFoundError(f"Katalog nie istnieje: {repo_path}")
        if not (self.repo_path / ".git").exists():
            raise FileNotFoundError(f"To nie jest repozytorium Git: {repo_path}")
        
        self.git_exe = r"C:\Program Files\Git\cmd\git.exe"
        if not Path(self.git_exe).exists():
            self.git_exe = "git"  # fallback
    
    def run_git(self, command):
        """Wykonaj komendę git i zwróć wynik"""
        try:
            result = subprocess.run(
                f'"{self.git_exe}" {command}',
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                shell=True
            )
            return result.stdout, result.stderr, result.returncode
        except Exception as e:
            return "", str(e), 1
    
    def status(self):
        """Pokaż status repozytorium"""
        stdout, stderr, code = self.run_git("status")
        return stdout if code == 0 else stderr
    
    def current_branch(self):
        """Pokaż aktualny branch"""
        stdout, _, code = self.run_git("rev-parse --abbrev-ref HEAD")
        return stdout.strip() if code == 0 else "unknown"
    
    def pull_test(self):
        """Pobierz najnowsze zmiany z branch 'test'"""
        print(f"📥 Pobieranie zmian z 'test'...")
        self.run_git("fetch origin")
        stdout, stderr, code = self.run_git("pull origin test")
        if code == 0:
            print("✅ Sukces! Pobrano zmiany z test")
            return True
        else:
            print(f"❌ Błąd: {stderr}")
            return False
    
    def push_to_test(self, message):
        """Wyślij zmiany do branch 'test'"""
        print(f"📤 Wysyłanie zmian do 'test'...")
        
        # Sprawdź czy są zmiany
        stdout, _, _ = self.run_git("status --porcelain")
        if not stdout.strip():
            print("⚠️  Brak zmian do commitu")
            return False
        
        # Add all
        self.run_git("add .")
        
        # Commit
        stdout, stderr, code = self.run_git(f'commit -m "{message}"')
        if code != 0:
            print(f"❌ Błąd przy commit: {stderr}")
            return False
        
        # Push
        stdout, stderr, code = self.run_git("push origin test")
        if code == 0:
            print("✅ Sukces! Wysłano commity do test")
            return True
        else:
            print(f"❌ Błąd przy push: {stderr}")
            return False
    
    def merge_test_to_master(self):
        """Merge branch 'test' do 'master'"""
        print("🔀 Mergowanie test → master...")
        
        # Przełącz na master
        stdout, stderr, code = self.run_git("checkout master")
        if code != 0:
            print(f"❌ Błąd: nie można przełączyć na master: {stderr}")
            return False
        
        # Pull master
        self.run_git("pull origin master")
        
        # Merge test
        stdout, stderr, code = self.run_git("merge test")
        if code == 0:
            print("✅ Merge udany!")
            
            # Push master
            stdout, stderr, code = self.run_git("push origin master")
            if code == 0:
                print("✅ Master zaktualizowany na GitHub")
                # Wróć na test
                self.run_git("checkout test")
                return True
            else:
                print(f"❌ Błąd przy push master: {stderr}")
                return False
        else:
            print(f"❌ Konflikt przy merge: {stderr}")
            return False
    
    def log_recent(self, count=5):
        """Pokaż ostatnie commity"""
        stdout, _, code = self.run_git(f"log --oneline -n {count}")
        return stdout if code == 0 else "Błąd przy log"
    
    def diff_files(self):
        """Pokaż zmiany w plikach"""
        stdout, _, code = self.run_git("diff --name-status")
        return stdout if code == 0 else "Brak zmian"
    
    def stash_changes(self):
        """Schowaj zmiany (backup)"""
        print("💾 Schowanie zmian...")
        stdout, stderr, code = self.run_git("stash")
        if code == 0:
            print("✅ Zmiany schowane (git stash)")
            return True
        else:
            print(f"❌ Błąd: {stderr}")
            return False
    
    def restore_stash(self):
        """Przywróć schowane zmiany"""
        print("📋 Przywracanie zmian...")
        stdout, stderr, code = self.run_git("stash pop")
        if code == 0:
            print("✅ Zmiany przywrócone")
            return True
        else:
            print(f"❌ Błąd: {stderr}")
            return False

def print_menu():
    print("\n" + "="*60)
    print("🎮 FOOTBALL SIM - GIT MANAGER")
    print("="*60)
    print("1️⃣  Status repozytorium")
    print("2️⃣  Pobierz zmiany z 'test' (git pull)")
    print("3️⃣  Wyślij zmiany do 'test' (git push)")
    print("4️⃣  Merge 'test' → 'master' (na GitHub)")
    print("5️⃣  Pokaż ostatnie commity")
    print("6️⃣  Pokaż zmienione pliki")
    print("7️⃣  Schowaj zmiany (stash)")
    print("8️⃣  Przywróć schowane zmiany")
    print("0️⃣  Wyjście")
    print("="*60)

def main():
    repo_path = r"C:\Users\luczkab\Desktop\moje\GGGRA202608\GIT\football_sim"
    
    try:
        manager = GitManager(repo_path)
    except FileNotFoundError as e:
        print(f"❌ Błąd: {e}")
        input("Naciśnij Enter aby wyjść...")
        sys.exit(1)
    
    while True:
        print(f"\n📍 Repozytorium: {repo_path}")
        print(f"🌿 Branch: {manager.current_branch()}")
        
        print_menu()
        choice = input("\nWybierz opcję (0-8): ").strip()
        
        if choice == "1":
            print("\n" + manager.status())
        
        elif choice == "2":
            manager.pull_test()
        
        elif choice == "3":
            message = input("Wpisz wiadomość commit: ").strip()
            if message:
                manager.push_to_test(message)
            else:
                print("⚠️  Wiadomość nie może być pusta")
        
        elif choice == "4":
            confirm = input("Czy na pewno chcesz mergować test → master? (t/n): ").lower()
            if confirm == "t":
                manager.merge_test_to_master()
        
        elif choice == "5":
            print("\n📜 Ostatnie commity:")
            print(manager.log_recent())
        
        elif choice == "6":
            print("\n📝 Zmienione pliki:")
            print(manager.diff_files())
        
        elif choice == "7":
            manager.stash_changes()
        
        elif choice == "8":
            manager.restore_stash()
        
        elif choice == "0":
            print("👋 Do widzenia!")
            break
        
        else:
            print("❌ Zła opcja")
        
        input("\nNaciśnij Enter aby kontynuować...")

if __name__ == "__main__":
    main()