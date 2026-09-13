from __future__ import annotations
from core.dice import Rng


def test_deterministic_same_seed():
    """Test 1: Rng(42) i Rng(42) daja identyczna sekwencje 100 rzutow."""
    rng1 = Rng(42)
    rng2 = Rng(42)
    
    sequence1 = rng1.roll_n(100)
    sequence2 = rng2.roll_n(100)
    
    assert sequence1 == sequence2, "Ta sama seed powinna generowac identyczne sekwencje"
    print("✓ Test 1 passed: Deterministic same seed")


def test_different_seeds():
    """Test 2: Rng(1) i Rng(2) daja rozne sekwencje."""
    rng1 = Rng(1)
    rng2 = Rng(2)
    
    sequence1 = rng1.roll_n(100)
    sequence2 = rng2.roll_n(100)
    
    assert sequence1 != sequence2, "Rozne seedy powinny generowac rozne sekwencje"
    print("✓ Test 2 passed: Different seeds produce different sequences")


def test_roll_range():
    """Test 3: Wszystkie wyniki roll() sa w zakresie 1..10 (1000 prob)."""
    rng = Rng(999)
    
    for _ in range(1000):
        result = rng.roll()
        assert 1 <= result <= 10, f"Wynik {result} poza zakresem [1, 10]"
    
    print("✓ Test 3 passed: All rolls in range [1, 10]")


def test_rolls_made_counter():
    """Test 4: rolls_made poprawnie zlicza rzuty, reseed() je zeruje."""
    rng = Rng(42)
    
    assert rng.rolls_made == 0
    
    rng.roll()
    assert rng.rolls_made == 1
    
    rng.roll_n(10)
    assert rng.rolls_made == 11
    
    rng.reseed(42)
    assert rng.rolls_made == 0
    
    print("✓ Test 4 passed: rolls_made counter and reseed work correctly")


def test_snapshot_restore():
    """Test 5: snapshot() + restore() odtwarza dokladnie te sama dalsza sekwencje."""
    rng1 = Rng(777)
    rng2 = Rng(777)
    
    # Wykonaj kilka rzutow
    rng1.roll_n(25)
    
    # Zapisz stan
    state = rng1.snapshot()
    
    # Wykonaj dalsze rzuty z rng1
    sequence1 = rng1.roll_n(50)
    
    # Przywroc stan w rng2 do tego samego miejsca
    rng2.roll_n(25)
    rng2.restore(state)
    
    # Dalsze rzuty powinny byc identyczne
    sequence2 = rng2.roll_n(50)
    
    assert sequence1 == sequence2, "Przywrocony stan nie generuje tej samej sekwencji"
    print("✓ Test 5 passed: Snapshot and restore work correctly")


if __name__ == "__main__":
    test_deterministic_same_seed()
    test_different_seeds()
    test_roll_range()
    test_rolls_made_counter()
    test_snapshot_restore()
    print("\n✅ Wszystkie testy przeszly!")