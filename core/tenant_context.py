from threading import local


_state = local()


def set_current_school(school):
    _state.school = school


def get_current_school():
    return getattr(_state, 'school', None)


def clear_current_school():
    if hasattr(_state, 'school'):
        delattr(_state, 'school')
