import math

# ==============================================================================
# ПРОГНОЗ МАЙСТЕРНОСТІ ГРАВЦЯ ПО РОКАХ
# Порт формули зі скрипту beScript (trainPlayerWithConditions): тренування, досвід, старіння.
# ==============================================================================

SKILLS = ['tckl', 'mrk', 'drbl', 'brcv', 'edrnc', 'pass', 'shotPwr', 'shotAcc']
SKILL_NAMES = {
    'tckl': 'Відбір', 'mrk': 'Опіка', 'drbl': 'Дриблінг', 'brcv': 'Прийом',
    'edrnc': 'Витривалість', 'pass': 'Пас', 'shotPwr': 'Сила удару', 'shotAcc': 'Точність удару',
}
REGIMES = {1: 'Мінімальні уміння', 2: 'По черзі', 3: 'Пропорційно', 4: 'Профільно'}
UNIQS = ['', 'Профильный', 'Работяга', 'Долгожитель']
TRAINS_PER_SEASON = 126

# Профільні уміння за лінією (для особливості «Профильный»: +20% до приросту)
PROFILE_SKILLS = {'DEF': ('tckl', 'mrk'), 'MID': ('brcv', 'pass'), 'ATT': ('shotPwr', 'shotAcc')}


def calc_talent(talent, exp_level):
    """Розрахунковий талант з профілю: талант + рівень досвіду / 10, але не більше 15.9"""
    return min(talent + exp_level / 10, 15.9)


def _js_round(x):
    return math.floor(x + 0.5)


def exp_limit(talent, exp_level, uniq):
    """Скільки очок досвіду потрібно для наступного рівня"""
    if uniq == 'Работяга':
        talent -= 1
    return math.floor(269 * math.pow(1.41, (exp_level + 89 * talent - 88) / 89)
                      * math.pow(math.factorial(talent), -0.11) * 89 / (99 - 10 * talent) + 0.00001)


def _pick_skill(skills, targets, regime, line, order):
    """Індекс уміння, яке тренуємо цього разу (або -1, якщо всі досягли цілі)"""
    below = [j for j in range(8) if targets[order[j]] > skills[order[j]]]
    if regime == 2:
        return below[0] if below else -1
    if regime == 3:
        return min(below, key=lambda j: skills[order[j]] / targets[order[j]]) if below else -1
    if regime == 4:
        profile = PROFILE_SKILLS.get(line, ())
        prof_below = [j for j in below if order[j] in profile]
        if prof_below:
            return prof_below[-1]
    return min(below, key=lambda j: skills[order[j]]) if below else -1


def project_growth(player, target_ages, settings):
    """
    Прогноз майстерності на початок кожного з вікових рубежів.
    player: dict(age, line('GK'/'DEF'/'MID'/'ATT'), power, skills{код: значення}, talent, exp_level, exp_points, uniq)
    settings: dict(coach_young, coach_adult, home_bonus, exp_gain, regime, targets{код: ціль},
                   trains_done, order[список кодів умінь у порядку тренування])
    Повертає {вік: (майстерність, розрахунковий талант)} для віків з target_ages (рубежі, до яких дійде гравець).
    """
    age = player['age']
    is_gk = player['line'] == 'GK'
    line = player['line']
    power = float(player['power'])
    skills = {s: float(player['skills'].get(s, 0.0)) for s in SKILLS}
    talent = int(player['talent'])
    exp_level = int(player['exp_level'])
    exp_points = float(player['exp_points'])
    uniq = player.get('uniq', '')

    order = settings.get('order') or SKILLS
    targets = settings['targets']
    regime = settings['regime']
    hb = 1.075 if settings.get('home_bonus') else 1.0
    trains_done = settings.get('trains_done', 0)

    wanted = sorted(set(a for a in target_ages if a >= age))
    result = {}
    if age in wanted:
        result[age] = (power, calc_talent(talent, exp_level))
    if not wanted:
        return result
    last_age = wanted[-1]

    # Вік, з якого починається старіння: 30, +1 воротар, +1 талант 2..7, ще +1 талант 3..5
    aging_age = 30 + (1 if is_gk else 0) + (1 if 2 <= talent <= 7 else 0) + (1 if 3 <= talent <= 5 else 0)
    aging_coef = 0.5 if uniq == 'Долгожитель' else 1.0

    while age < last_age:
        if is_gk:
            skill_key = order[0]
        else:
            j = _pick_skill(skills, targets, regime, line, order)
            # усі цілі досягнуто: у скрипті випадкове уміння, тут беремо найслабше
            skill_key = order[j] if j >= 0 else min(SKILLS, key=lambda s: skills[s])

        fact_gift = min(talent + exp_level / 10, 16)
        coach = settings['coach_adult'] if age >= 24 else settings['coach_young']
        age_dev = abs(age - 22.5)
        add = max(_js_round(
            1000 * (1 + coach / 100) * hb / 1.03 * 100
            * math.pow(3 * 2.745 * 0.13 + math.pow(fact_gift, 0.6) * 0.6, 2)
            / (19 + math.pow(skills[skill_key] / (7.7 if is_gk else 1), 2)) / 50
            * (-0.1082 * age_dev ** 2 - 2.526 * age_dev + 101.17) / 100
            * (1 - math.pow(power, 0.6) * (0.019 - fact_gift * 0.001))
        ) / 1000, 0)
        if uniq == 'Профильный' and skill_key in PROFILE_SKILLS.get(line, ()):
            add *= 1.2
        power += add
        skills[skill_key] += add

        if age >= aging_age:
            loss = (0.015 + 0.015 * (age - aging_age + 1)) * aging_coef
            power -= loss
            # у скрипті зменшується випадкове уміння, тут ділимо порівну
            if is_gk:
                skills[order[0]] -= loss
            else:
                for s in SKILLS:
                    skills[s] -= loss / 8

        pending = None
        trains_done += 1
        carry = math.floor(trains_done / (TRAINS_PER_SEASON + 1) + 0.001)
        if carry:
            age += carry
            trains_done -= carry * TRAINS_PER_SEASON
            if age in wanted:
                pending = (age, power)  # талант запишемо після нарахування досвіду цього кроку

        if fact_gift < 15.9:
            exp_points += settings['exp_gain'] / TRAINS_PER_SEASON
        limit = exp_limit(talent, exp_level, uniq)
        levels = math.floor(exp_points / limit + 0.00001)
        exp_level += levels
        exp_points -= levels * limit
        if pending:
            result[pending[0]] = (pending[1], calc_talent(talent, exp_level))

    return result
