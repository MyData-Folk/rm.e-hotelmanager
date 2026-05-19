from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


def apply_step(value: float, operation: str, amount: float) -> float:
    if operation == 'multiplier':
        return value * amount

    if operation == 'offset':
        return value + amount

    if operation == 'fixed':
        return amount

    if operation == 'percentage_discount':
        return value * (1 - amount / 100)

    if operation == 'percentage_markup':
        return value * (1 + amount / 100)

    raise ValueError(f'Unknown operation: {operation}')


def apply_rounding(value: float, mode: str = 'two_decimals', increment: float | None = None) -> float:
    d = Decimal(str(value))

    if mode == 'none':
        return float(d)

    if mode == 'two_decimals':
        return float(d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    if mode == 'nearest_euro':
        return float(d.quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    if mode == 'ceil_euro':
        return float(d.to_integral_value(rounding=ROUND_CEILING))

    if mode == 'floor_euro':
        return float(d.to_integral_value(rounding=ROUND_FLOOR))

    if mode in {'nearest_increment', 'ceil_increment', 'floor_increment'}:
        inc = Decimal(str(increment or 1))
        divided = d / inc

        if mode == 'nearest_increment':
            rounded = divided.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        elif mode == 'ceil_increment':
            rounded = divided.to_integral_value(rounding=ROUND_CEILING)
        else:
            rounded = divided.to_integral_value(rounding=ROUND_FLOOR)

        return float(rounded * inc)

    raise ValueError(f'Unknown rounding mode: {mode}')


def calculate_plan_from_rule(base_price: float, rule, steps: list) -> dict:
    value = base_price
    trace = []

    for step in sorted(steps, key=lambda item: item.step_order):
        before = value
        value = apply_step(value, step.operation, step.value)
        trace.append({
            'step_order': step.step_order,
            'operation': step.operation,
            'value': step.value,
            'before': before,
            'after': value,
        })

    raw_result = value
    rounded_result = apply_rounding(
        raw_result,
        getattr(rule, 'rounding_mode', 'two_decimals'),
        getattr(rule, 'rounding_increment', None),
    )

    return {
        'raw_result': raw_result,
        'rounded_result': rounded_result,
        'rounding_mode': getattr(rule, 'rounding_mode', 'two_decimals'),
        'trace': trace,
    }
