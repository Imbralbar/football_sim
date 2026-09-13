"""Wszystkie parametry gry w jednym miejscu."""

# ---------- BOISKO ----------
FIELD_W, FIELD_H = 25, 17
PENALTY_DEPTH, PENALTY_H = 4, 11
GOAL_AREA_DEPTH, GOAL_AREA_H = 2, 5
GOAL_H = 3
PENALTY_SPOT_DEPTH = 3

# ---------- CZAS / PRĘDKOŚĆ RUCHU ----------
TICKS_PER_ACTION   = 36     # NWW z 12, 9, 6
CARRIER_MOVE_EVERY = 4      # carrier: 9 kroków/akcję — WOLNIEJSZY (było 3 -> 12 kroków)
PLAYER_MOVE_EVERY  = 3      # wszyscy pozostali (w tym obrońcy): 12 kroków/akcję — SZYBSI (było 4 -> 9)
DUEL_CONTACT_TICKS = 6      # 1/6 akcji — próg styczności do starcia
PROTECTION_ACTIONS = 2
PROTECTION_SCOPE   = "PAIR"     # "PAIR" | "ALL"   (patrz O-2)

# Uwaga (v0.5): carrier jest teraz WOLNIEJSZY niż każdy broniący.
# Jego jedyna przewaga to wygrany duel (dribble) -> BEAT_DEFENDER + karencja
# dla pokonanego obrońcy (patrz DUEL_* niżej). Nie ma już osobnej,
# szybszej cadencji dla presserów — CHASERS różnią się CELEM ruchu, nie prędkością.

# ---------- RUCH / FORMACJA (v2) ----------
CHASERS = 2   # ZAWSZE dokładnie 2 najbliżsi obrońcy szarżują wprost na piłkę (stała, nie zależy od stylu)

# FORMATION_FOLLOW (v0.4.1) zastąpione rozdzieleniem osi głębokości/szerokości:
#  - głębokość -> DEF_LINE_* (przesuw linii wg fazy ATTACK/DEFENSE)
#  - szerokość -> FORMATION_LATERAL_FOLLOW (ślizg bloku w stronę piłki w poziomie)
FORMATION_LATERAL_FOLLOW = {
    "DEF": 0.6,   # obrona ślizga się mocno w stronę piłki
    "MID": 0.5,
    "FWD": 0.3,   # napastnicy zostają rozciągnięci szeroko/wysoko pod kontratak
}
FORMATION_COMPACTNESS = 0.15   # o ile linia ściska się do środka w fazie DEFENSE (0 = wyłączone)

# ---------- PRESSING ----------
PRESS_TRIGGER_DIST = 4                 # poza tym dystansem CHASERS nie ruszają wprost na piłkę
PRESS_ROLES        = ("DEF", "MID")    # kto może być wybrany jako jeden z CHASERS
MARKING_RADIUS     = 6                 # max dystans przypisania markowania 1v1

# ---------- DYNAMICZNA LINIA OBRONY ----------
DEF_LINE_PUSH_ATTACK  = 3     # o ile linia wypycha się do przodu w ataku
DEF_LINE_DROP_DEFENSE = 2     # o ile linia cofa się w obronie
MID_TRACKBACK         = True  # czy MID też cofa linię (recovery run)

# ---------- DUELE WIELOOSOBOWE I KARENCJE ----------
DUEL_MAX_DEFENDERS          = 2   # ilu obrońców może naraz wejść w starcie o piłkę
DUEL_COOLDOWN_DEFENDER      = 2   # akcje karencji dla obrońcy uczestniczącego w starciu (stoi w miejscu)
DUEL_COOLDOWN_ATTACKER_LOSS = 1   # akcje karencji dla zawodnika, który stracił piłkę (nie może bronić/pressować)

# ---------- STYL DRUŻYNY (asymetria AI — gotowe pod PvC i etap 2) ----------
TEAM_STYLE_DEFAULT = {
    "press_intensity":     "MEDIUM",  # LOW | MEDIUM | HIGH -> zarezerwowane na przyszłość (obecnie CHASERS=2 na sztywno)
    "defensive_line":      "MEDIUM",  # LOW | MEDIUM | HIGH -> mnożnik DEF_LINE_*
    "possession_bias":     0,         # zarezerwowane – etap 2 (utrzymanie posiadania)
    "counter_attack_bias": 0,         # zarezerwowane – etap 2 (kontratak)
}
DEF_LINE_MULT = {"LOW": 0.5, "MEDIUM": 1.0, "HIGH": 1.5}

# ---------- STATYSTYKI ----------
BASE_STATS = {
    "DEF": {"stamina": 800, "d_dribble": 15, "d_shot": 15, "d_pass": 15,
            "dribble": 5,  "shot": 5,  "passing": 5},
    "MID": {"stamina": 800, "d_dribble": 10, "d_shot": 10, "d_pass": 10,
            "dribble": 10, "shot": 10, "passing": 10},
    "FWD": {"stamina": 800, "d_dribble": 5,  "d_shot": 5,  "d_pass": 5,
            "dribble": 15, "shot": 15, "passing": 15},
    "GK":  {"stamina": 800, "passing": 20, "punch": 20, "catch": 20},
}

# ---------- ROZSTRZYGNIECIA (v0.3) ----------
DICE_SIDES = 10
MISMATCH_PENALTY = -6
PAIRS = {2: 5, 3: 6, 4: 7}       # obrona -> sparowana akcja
AIR_INTERCEPT_BONUS = 3          # premia obrońcy przy piłce w powietrzu

TIE_GROUND_TO_ATTACKER = True    # starcie: remis -> atakujący  (O-1)
TIE_AIR_TO_DEFENDER    = True    # przechwyt: remis -> obrońca  (O-1)

# Bramkarz
GK_TIE_CATCH_FAILS = True        # remis przy 9 (łapanie) -> nie łapie
GK_PUNCH_MIN, GK_PUNCH_MAX = 2, 4   # zasięg wybicia po piąstkowaniu

# ---------- AI ----------
THREAT_DISTANCE = 3
PASS_MIN_GAIN   = 2
PASS_PENALIZE_SAME_ROLE = True

# Zasięg strzału wg roli (Chebyshev) — obcięte względem v0.4.1 (9/6), bo dawały za dużo goli
FWD_SHOT_RANGE  = 6     # było 9
MID_SHOT_RANGE  = 4     # było 6
DEF_SHOT_RANGE  = 0
SHOT_RANGE      = FWD_SHOT_RANGE   # wsteczna kompatybilność

# ---------- FAZY GRY ----------
PHASE_ATTACK  = "ATTACK"
PHASE_DEFENSE = "DEFENSE"
PHASE_NEUTRAL = "NEUTRAL"     # piłka wolna / bez carriery

# ---------- PENALTIES ----------
POST_CHANCE = 5  # szansa na słupek przy strzale LEFT/RIGHT (%)

# ---------- RENDER ----------
CELL = 32
BALL_GLYPH = "o"
COL_GRASS_A = (32, 110, 55)
COL_GRASS_B = (28, 100, 50)
COL_LINE    = (235, 240, 235)
COL_TEAM_A  = (25, 60, 220)
COL_TEAM_B  = (15, 15, 15)
COL_CHIP    = (245, 245, 240)
COL_CONTACT = (230, 60, 60)
COL_BG      = (18, 62, 32)
# ---------- BRAMKARZ: DRYBLING PO OBRONIE (v0.6) ----------
GK_DRIBBLE_STAT             = 8     # bazowa umiejętność dryblingu bramkarza (brak własnej stat. 'dribble')
GK_INITIAL_DRIBBLE_CHANCE   = 0.10  # 10% szans na próbę wybiegu zamiast podania po złapaniu
GK_DRIBBLE_CHANCE_AFTER_WIN = 0.05  # po 1. wygranej: kolejna szansa = 5%, dalej x0.5 po każdej wygranej
GK_DRIBBLE_MIN_CHANCE       = 0.01  # poniżej progu — bramkarz zawsze podaje
GK_LOST_BALL_SHOT_BONUS     = 0.5   # +50% do shot_value dla zawodnika, który odebrał piłkę biegnącemu GK