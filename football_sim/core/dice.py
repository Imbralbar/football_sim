from __future__ import annotations
import random
from dataclasses import dataclass, field
import config as C


@dataclass
class Rng:
    """Deterministyczny generator. Kazde uzycie jest liczone i logowane."""
    seed: int = 0
    _rng: random.Random = field(init=False, repr=False)
    rolls_made: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        """Inicjalizacja instancji random.Random z sedem."""
        self._rng = random.Random(self.seed)
        self.rolls_made = 0

    def roll(self) -> int:
        """Rzut k10. Zwraca 1..C.DICE_SIDES. Inkrementuje rolls_made."""
        self.rolls_made += 1
        return self._rng.randint(1, C.DICE_SIDES)

    def roll_n(self, n: int) -> list[int]:
        """n rzutow k10."""
        return [self.roll() for _ in range(n)]

    def choice(self, seq: list) -> object:
        """Deterministyczny wybor elementu. Rzuca ValueError dla pustej listy."""
        if not seq:
            raise ValueError("Nie mozna wybrac elementu z pustej listy")
        return self._rng.choice(seq)

    def randint(self, a: int, b: int) -> int:
        """Deterministyczna liczba calkowita z przedzialu [a, b] wlacznie."""
        return self._rng.randint(a, b)

    def reseed(self, seed: int) -> None:
        """Restart generatora. Zeruje rolls_made."""
        self.seed = seed
        self._rng = random.Random(seed)
        self.rolls_made = 0

    def snapshot(self) -> tuple:
        """Stan wewnetrzny generatora - do zapisu/odtworzenia meczu."""
        return (self.seed, self._rng.getstate(), self.rolls_made)

    def restore(self, state: tuple) -> None:
        """Przywraca stan z snapshot()."""
        seed, rng_state, rolls_made = state
        self.seed = seed
        self._rng.setstate(rng_state)
        self.rolls_made = rolls_made