import time

class TimeSyncer:
    def __init__(self, max_time_interval = None):
        self.relative_time = 0.0
        self.last_time = None
        self.max_time_interval = max_time_interval
    
    def get_relative_time(self):
        if self.last_time is None:
            self.last_time = time.time()
        else:
            current_time = time.time()
            time_interval = current_time - self.last_time
            self.last_time = current_time
            if self.max_time_interval and time_interval > self.max_time_interval:
                time_interval = self.max_time_interval
            self.relative_time += time_interval
        return self.relative_time

    def reset(self):
        self.relative_time = 0.0
        self.last_time = None