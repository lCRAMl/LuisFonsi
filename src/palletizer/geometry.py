"""Einfache Geometrie-Hilfsfunktionen für achsparallele Rechtecke."""


def extent(count: int, size: float, gap: float) -> float:
    """Ausdehnung von `count` Kartons der Größe `size` mit Spaltmaß `gap`.

    D = n * a + (n - 1) * g
    """
    return count * size + (count - 1) * gap


def rect_overlap(ax1: float, ax2: float, ay1: float, ay2: float,
                 bx1: float, bx2: float, by1: float, by2: float,
                 eps: float) -> bool:
    """True, wenn sich zwei Rechtecke mit einer Fläche > 0 überlappen.

    Überlappung in X: ox = min(ax2, bx2) - max(ax1, bx1)
    Überlappung in Y: oy = min(ay2, by2) - max(ay1, by1)
    Reine Berührung an einer Kante oder Ecke zählt nicht (ox bzw. oy <= eps).
    """
    ox = min(ax2, bx2) - max(ax1, bx1)
    oy = min(ay2, by2) - max(ay1, by1)
    return ox > eps and oy > eps
