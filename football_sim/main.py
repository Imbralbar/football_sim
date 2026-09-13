from core.field import Field
from core.entities import Side
from core.formation import build_442
from core.match import Match
from core.dice import Rng
from render.pygame_view import PitchView
import pygame


def main() -> None:
    # Inicjalizacja
    field = Field()
    home = build_442(field, "Blues", Side.LEFT, "A")
    away = build_442(field, "Blacks", Side.RIGHT, "B")
    rng = Rng(seed=42)  # Deterministyczny mecz
    
    # Utworzenie meczu
    match = Match(home, away, field, rng, enable_extra_time=False)
    
    # Inicjalizacja pygame i renderera
    pygame.init()
    view = PitchView(field)
    view.screen = pygame.display.set_mode(
        (field.w * view.cell + 200, field.h * view.cell + 100)
    )
    pygame.display.set_caption("Football Sim - Live Match")
    view.clock = pygame.time.Clock()
    
    # Rozgrywka z wizualizacja
    result = match.play_with_render(view)
    
    # Wynik koncowy
    print(f"\n{'='*50}")
    print(f"WYNIK KONCOWY:")
    print(f"{result.home_score} - {result.away_score}")
    if result.winner:
        winner_name = match.home.name if result.winner == "home" else match.away.name
        print(f"Zwyciezca: {winner_name}")
    else:
        print("Remis!")
    print(f"{'='*50}\n")
    
    pygame.quit()


if __name__ == "__main__":
    main()