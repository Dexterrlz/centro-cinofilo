DISCIPLINE_COLORS = {
    'agility':             '#E8621A',
    'agility campo 1':     '#E8621A',
    'agility campo 2':     '#F5A030',
    'swim dog sport':      '#378ADD',
    'educazione di base':  '#34C759',
    'hoopers':             '#AF52DE',
    'rally obedience':     '#FF6B6B',
    'nosework':            '#FFB347',
}


def discipline_color(name: str) -> str:
    return DISCIPLINE_COLORS.get(name.lower().strip(), '#888787')
