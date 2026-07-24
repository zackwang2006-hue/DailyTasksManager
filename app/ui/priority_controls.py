def sync_priority_controls(important_checkbox, urgent_checkbox, fixed_event_checkbox, fixed_time_widgets):
    fixed_widgets = tuple(fixed_time_widgets)
    has_priority = important_checkbox.isChecked() or urgent_checkbox.isChecked()
    is_fixed = fixed_event_checkbox.isChecked()

    if has_priority and is_fixed:
        fixed_event_checkbox.blockSignals(True)
        fixed_event_checkbox.setChecked(False)
        fixed_event_checkbox.blockSignals(False)
        is_fixed = False

    if is_fixed:
        for checkbox in (important_checkbox, urgent_checkbox):
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
            checkbox.setEnabled(False)
        fixed_event_checkbox.setEnabled(True)
        for widget in fixed_widgets:
            widget.setEnabled(True)
        return

    important_checkbox.setEnabled(True)
    urgent_checkbox.setEnabled(True)
    fixed_event_checkbox.setEnabled(not has_priority)
    for widget in fixed_widgets:
        widget.setEnabled(False)


def connect_priority_controls(important_checkbox, urgent_checkbox, fixed_event_checkbox, fixed_time_widgets):
    callback = lambda *args: sync_priority_controls(
        important_checkbox,
        urgent_checkbox,
        fixed_event_checkbox,
        fixed_time_widgets,
    )
    important_checkbox.stateChanged.connect(callback)
    urgent_checkbox.stateChanged.connect(callback)
    fixed_event_checkbox.stateChanged.connect(callback)
    return callback
