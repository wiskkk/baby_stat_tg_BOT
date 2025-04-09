def format_minutes(minutes: int) -> str:
    hours = minutes // 60
    mins = minutes % 60
    if hours > 0:
        return f"{hours} ч {mins} мин"
    return f"{mins} мин"
