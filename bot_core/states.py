from aiogram.fsm.state import State, StatesGroup


class SleepTimeState(StatesGroup):
    waiting_for_time = State()
    waiting_for_end_time = State()


class ManualSleepStartState(StatesGroup):
    waiting_for_time = State()
    waiting_for_date_choice = State()


class ManualEndSleepState(StatesGroup):
    waiting_for_time = State()
    waiting_for_date_choice = State()
