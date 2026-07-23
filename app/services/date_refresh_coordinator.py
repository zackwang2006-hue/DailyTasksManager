from datetime import datetime, time, timedelta

from PySide6.QtCore import QObject, QTimer, Signal

from app.services.period_service import period_service


class DateRefreshCoordinator(QObject):
    date_changed = Signal(object, object)

    def __init__(self, parent=None, watchdog_interval_ms=300000):
        super().__init__(parent)
        self.last_known_date = period_service.get_local_today()

        self.midnight_timer = QTimer(self)
        self.midnight_timer.setSingleShot(True)
        self.midnight_timer.timeout.connect(self.check_date_change)

        self.watchdog_timer = QTimer(self)
        self.watchdog_timer.setInterval(watchdog_interval_ms)
        self.watchdog_timer.timeout.connect(self.check_date_change)

    def start(self):
        self.schedule_next_midnight()
        self.watchdog_timer.start()

    def check_date_change(self):
        current_date = period_service.get_local_today()
        if current_date != self.last_known_date:
            old_date = self.last_known_date
            self.last_known_date = current_date
            self.date_changed.emit(old_date, current_date)
        self.schedule_next_midnight()

    def force_refresh_current_date(self):
        self.schedule_next_midnight()
        return self.last_known_date

    def schedule_next_midnight(self):
        self.midnight_timer.start(self.milliseconds_until_next_midnight())

    def milliseconds_until_next_midnight(self):
        now = datetime.now()
        next_midnight = datetime.combine(now.date() + timedelta(days=1), time.min)
        return max(1000, int((next_midnight - now).total_seconds() * 1000))
