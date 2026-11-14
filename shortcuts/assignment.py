"""Display portal descriptions verbatim; compare only recognizable key labels."""
import re


def comparison(requested: str, assigned: str) -> str:
    """Return match/different/unknown. Portal descriptions may be localized prose."""
    def tokens(value):
        value = re.sub(r'^Press\s+', '', value.strip(), flags=re.IGNORECASE)
        value = re.sub(r'<([^>]+)>', r'\1+', value)
        parts = value.split('+')
        if len(parts) < 2 or not re.fullmatch(r'[A-Za-z0-9_]+', parts[-1]):
            return None
        aliases = {'ctrl': 'CTRL', 'control': 'CTRL', 'alt': 'ALT', 'shift': 'SHIFT',
                   'super': 'LOGO', 'logo': 'LOGO', 'win': 'LOGO', 'num': 'NUM'}
        mods = [aliases.get(part.strip().lower()) for part in parts[:-1]]
        if any(mod is None for mod in mods):
            return None
        return frozenset(mods), parts[-1].casefold()
    expected, actual = tokens(requested), tokens(assigned)
    if expected is None or actual is None:
        return 'unknown'
    return 'match' if expected == actual else 'different'


def display_shortcut(value: str) -> str:
    """Format recognized XDG/English portal key labels; preserve other prose."""
    candidate = re.sub(r'^Press\s+', '', value.strip(), flags=re.IGNORECASE)
    candidate = re.sub(r'<([^>]+)>', r'\1+', candidate)
    parts = candidate.split('+')
    aliases = {'ctrl': 'Ctrl', 'control': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift',
               'super': 'Super', 'logo': 'Super', 'win': 'Super', 'num': 'Num'}
    mods = [aliases.get(part.strip().lower()) for part in parts[:-1]]
    if len(parts) < 2 or any(mod is None for mod in mods) or not re.fullmatch(r'[A-Za-z0-9_]+', parts[-1]):
        return value
    # Use a consistent readable order regardless of backend modifier order.
    order = ['Ctrl', 'Alt', 'Shift', 'Super', 'Num']
    key = parts[-1].upper() if len(parts[-1]) == 1 else parts[-1]
    return '+'.join([mod for mod in order if mod in mods] + [key])
