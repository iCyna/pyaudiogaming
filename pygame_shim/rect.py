# -*- coding: utf-8 -*-
"""Pure-Python pygame.Rect implementation."""


class Rect:
    __slots__ = ("x", "y", "width", "height")

    def __init__(self, *args):
        if len(args) == 1:
            a = args[0]
            if isinstance(a, Rect):
                self.x, self.y, self.width, self.height = a.x, a.y, a.width, a.height
            elif len(a) == 4:
                self.x, self.y, self.width, self.height = int(a[0]), int(a[1]), int(a[2]), int(a[3])
            elif len(a) == 2:
                self.x, self.y = int(a[0][0]), int(a[0][1])
                self.width, self.height = int(a[1][0]), int(a[1][1])
            else:
                raise TypeError("Invalid Rect argument")
        elif len(args) == 2:
            self.x, self.y = int(args[0][0]), int(args[0][1])
            self.width, self.height = int(args[1][0]), int(args[1][1])
        elif len(args) == 4:
            self.x, self.y, self.width, self.height = int(args[0]), int(args[1]), int(args[2]), int(args[3])
        else:
            raise TypeError("Rect expects 1, 2, or 4 arguments")

    @property
    def w(self):
        return self.width

    @w.setter
    def w(self, val):
        self.width = int(val)

    @property
    def h(self):
        return self.height

    @h.setter
    def h(self, val):
        self.height = int(val)

    @property
    def left(self):
        return self.x

    @left.setter
    def left(self, val):
        self.x = int(val)

    @property
    def top(self):
        return self.y

    @top.setter
    def top(self, val):
        self.y = int(val)

    @property
    def right(self):
        return self.x + self.width

    @right.setter
    def right(self, val):
        self.x = int(val) - self.width

    @property
    def bottom(self):
        return self.y + self.height

    @bottom.setter
    def bottom(self, val):
        self.y = int(val) - self.height

    @property
    def centerx(self):
        return self.x + self.width // 2

    @centerx.setter
    def centerx(self, val):
        self.x = int(val) - self.width // 2

    @property
    def centery(self):
        return self.y + self.height // 2

    @centery.setter
    def centery(self, val):
        self.y = int(val) - self.height // 2

    @property
    def center(self):
        return (self.centerx, self.centery)

    @center.setter
    def center(self, val):
        self.centerx, self.centery = int(val[0]), int(val[1])

    @property
    def topleft(self):
        return (self.x, self.y)

    @property
    def topright(self):
        return (self.right, self.y)

    @property
    def bottomleft(self):
        return (self.x, self.bottom)

    @property
    def bottomright(self):
        return (self.right, self.bottom)

    @property
    def size(self):
        return (self.width, self.height)

    @size.setter
    def size(self, val):
        self.width, self.height = int(val[0]), int(val[1])

    def copy(self):
        return Rect(self.x, self.y, self.width, self.height)

    def move(self, dx, dy):
        return Rect(self.x + int(dx), self.y + int(dy), self.width, self.height)

    def inflate(self, dx, dy):
        dx, dy = int(dx), int(dy)
        return Rect(self.x - dx // 2, self.y - dy // 2, self.width + dx, self.height + dy)

    def collidepoint(self, *args):
        if len(args) == 1:
            px, py = args[0]
        else:
            px, py = args[0], args[1]
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height

    def colliderect(self, other):
        o = other if isinstance(other, Rect) else Rect(other)
        return (
            self.x < o.x + o.width
            and self.x + self.width > o.x
            and self.y < o.y + o.height
            and self.y + self.height > o.y
        )

    def __len__(self):
        return 4

    def __getitem__(self, idx):
        return (self.x, self.y, self.width, self.height)[idx]

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.width
        yield self.height

    def __repr__(self):
        return f"<rect({self.x}, {self.y}, {self.width}, {self.height})>"
