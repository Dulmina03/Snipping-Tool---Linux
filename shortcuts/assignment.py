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
