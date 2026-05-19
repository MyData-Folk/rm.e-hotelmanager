def normalize_availability_value(value):
    raw = '' if value is None else str(value).strip().lower()

    if raw == 'x':
        return {
            'raw_value': 'x',
            'available_quantity': None,
            'status': 'not_available_for_sale',
            'label': 'Non disponible à la vente',
        }

    if raw == '0':
        return {
            'raw_value': '0',
            'available_quantity': 0,
            'status': 'sold_out',
            'label': 'Stock épuisé',
        }

    try:
        quantity = int(float(raw))
    except ValueError:
        return {
            'raw_value': raw,
            'available_quantity': None,
            'status': 'unknown',
            'label': 'Valeur non reconnue',
        }

    if 1 <= quantity <= 100:
        return {
            'raw_value': str(quantity),
            'available_quantity': quantity,
            'status': 'available',
            'label': f'{quantity} chambre(s) en vente',
        }

    return {
        'raw_value': raw,
        'available_quantity': quantity,
        'status': 'out_of_range',
        'label': 'Valeur hors plage attendue',
    }
