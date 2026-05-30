import pandas as pd
import pandas_market_calendars as mcal


class MarketCalendarAligner:
    def __init__(self, exchange="NYSE"):
        self.calendar = mcal.get_calendar(exchange)

        
    def get_schedule(self, start_date, end_date=None):
        """
        Generate trading schedule dynamically.
        If end_date is None → use today.
        """
        if end_date is None:
            end_date = pd.Timestamp.today().date()

        return self.calendar.schedule(
            start_date=start_date,
            end_date=end_date
        )

    def align(self, dt, schedule):
        dt = pd.to_datetime(dt)
        current_day = pd.Timestamp(dt.date())

        if current_day in schedule.index:
            market_open = (
                schedule.loc[current_day, "market_open"]
                .tz_convert("America/New_York")
                .tz_localize(None)
            )

            market_close = (
                schedule.loc[current_day, "market_close"]
                .tz_convert("America/New_York")
                .tz_localize(None)
            )

            if market_open <= dt < market_close:
                return dt.ceil("30min")

            elif dt < market_open:
                return market_open

        next_sessions = schedule[schedule.index > current_day]
        next_open = (
            next_sessions.iloc[0]["market_open"]
            .tz_convert("America/New_York")
            .tz_localize(None)
        )

        return next_open
