ROOM_RULES = {
    'Double Classique': {'operation': 'offset', 'value': 0},
    'Double Single Use Classique': {'operation': 'offset', 'value': 0},
    'Twin Classique': {'operation': 'offset', 'value': 10},
    'Double Classique Terrasse': {'operation': 'offset', 'value': 50},
    'Double Deluxe': {'operation': 'offset', 'value': 70},
    'Twin Deluxe': {'operation': 'offset', 'value': 80},
    'Double Deluxe Terrasse': {'operation': 'offset', 'value': 120},
    'Deux Chambres Adjacentes 4 personnes': {'operation': 'multiplier_offset', 'multiplier': 2, 'offset': 60},
}


def calculate_room_reference_price(base_price: float, room_name: str) -> float:
    rule = ROOM_RULES.get(room_name)
    if not rule:
        return base_price

    operation = rule['operation']

    if operation == 'offset':
        return base_price + rule['value']

    if operation == 'multiplier_offset':
        return base_price * rule.get('multiplier', 1) + rule.get('offset', 0)

    raise ValueError(f'Unknown room rule operation: {operation}')
