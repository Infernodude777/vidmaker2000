import time


class PreviewPlayer:
    def __init__(self, fps=30.0):
        self.fps = fps
        self.playing = False
        self.speed = 1.0
        self.t = 0.0
        self.loop = True
        self.in_point = 0.0
        self.out_point = 0.0
        self._last = None

    def play(self):
        self.playing = True
        self._last = time.time()

    def pause(self):
        self.playing = False
        self._last = None

    def toggle(self):
        if self.playing:
            self.pause()
        else:
            self.play()

    def seek(self, t):
        self.t = max(0.0, t)

    def tick(self, total):
        if not self.playing:
            return self.t
        now = time.time()
        dt = now - (self._last or now)
        self._last = now
        self.t += dt * self.speed
        if self.out_point > 0 and self.t >= self.out_point:
            self.t = self.in_point if self.loop else self.out_point
        elif self.t >= total:
            self.t = self.in_point if self.loop else 0.0
        return self.t
