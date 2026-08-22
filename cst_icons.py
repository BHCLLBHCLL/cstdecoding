# -*- coding: utf-8 -*-
"""QPainter vector icons for cst_gui (cabdecoding AppIcons pattern, CST-colored).

Drawn in normalized 0–1 coordinates so every glyph fills the same optical box
at ribbon (36px), QAT (22px) and Navigation Tree (22px) sizes. HiDPI paint is
2× with devicePixelRatio so edges stay sharp.
"""

from __future__ import annotations

import math

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF, QRadialGradient,
)


class AppIcons:
    """HiDPI vector icons for ribbon / tree / toolbars (CST-sized)."""

    _cache: dict[tuple, QIcon] = {}
    _sz = 32
    _dpr = 2

    @classmethod
    def get(cls, name: str, size: int = 32) -> QIcon:
        key = (name, size)
        if key not in cls._cache:
            cls._cache[key] = QIcon(cls._paint(name, size))
        return cls._cache[key]

    @classmethod
    def _paint(cls, name: str, size: int) -> QPixmap:
        dpr = cls._dpr
        cls._sz = size
        px = max(1, int(round(size * dpr)))
        pm = QPixmap(px, px)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        m = max(0.4, size * 0.035)
        r = QRectF(m, m, size - 2 * m, size - 2 * m)
        if name.startswith("matsphere_"):
            try:
                rgb = tuple(int(x) for x in name.split("_")[1:4])
            except ValueError:
                rgb = (80, 170, 190)
            cls._paint_mat_sphere(p, r, rgb)
        else:
            drawer = getattr(cls, f"_draw_{name}", None)
            if drawer:
                drawer(p, r, size)
            else:
                cls._draw_generic(p, r, size)
        p.end()
        return pm

    @classmethod
    def material(cls, rgb, size: int = 16) -> QIcon:
        r, g, b = (max(0, min(255, int(c))) for c in rgb)
        return cls.get(f"matsphere_{r}_{g}_{b}", size)

    # -- geometry helpers --------------------------------------------------

    @classmethod
    def _pen(cls, color, w=1.35):
        scaled = max(0.9, min(3.6, w * (cls._sz / 32.0)))
        pen = QPen(QColor(color))
        pen.setWidthF(scaled)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        return pen

    @staticmethod
    def _grad(r, c1, c2, vertical=True):
        g = QLinearGradient(
            r.topLeft(),
            r.bottomLeft() if vertical else r.topRight())
        g.setColorAt(0.0, QColor(c1))
        g.setColorAt(1.0, QColor(c2))
        return QBrush(g)

    @staticmethod
    def _pt(r, x, y):
        return QPointF(r.left() + r.width() * x, r.top() + r.height() * y)

    @classmethod
    def _poly(cls, r, pts):
        return QPolygonF([cls._pt(r, x, y) for x, y in pts])

    @staticmethod
    def _box(r, x, y, w, h):
        return QRectF(r.left() + r.width() * x, r.top() + r.height() * y,
                      r.width() * w, r.height() * h)

    @staticmethod
    def _rad(r, frac=0.12):
        return max(1.4, min(r.width(), r.height()) * frac)

    @staticmethod
    def _font(r, frac=0.46, bold=True):
        f = QFont("Segoe UI")
        f.setPixelSize(max(8, int(round(min(r.width(), r.height()) * frac))))
        f.setBold(bold)
        return f

    @classmethod
    def _fill_round(cls, p, r, c1, c2, outline, rad=None, sheen=True):
        rad = cls._rad(r) if rad is None else rad
        p.setPen(cls._pen(outline, 1.15))
        p.setBrush(cls._grad(r, c1, c2))
        p.drawRoundedRect(r, rad, rad)
        if sheen:
            p.setPen(Qt.NoPen)
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0.0, QColor(255, 255, 255, 78))
            g.setColorAt(0.42, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(g))
            inset = QRectF(r).adjusted(0.4, 0.4, -0.4, -0.4)
            p.drawRoundedRect(inset, rad, rad)

    @classmethod
    def _draw_generic(cls, p, r, _s=0):
        cls._fill_round(p, r, "#e3f2fd", "#90caf9", "#1565c0")

    # -- file / clipboard --------------------------------------------------

    @classmethod
    def _draw_open(cls, p, r, _s):
        tab = cls._box(r, 0.0, 0.02, 0.50, 0.32)
        p.setPen(cls._pen("#c47a00", 1.2))
        p.setBrush(cls._grad(tab, "#ffe082", "#f9a825"))
        p.drawRoundedRect(tab, cls._rad(r, 0.08), cls._rad(r, 0.08))
        body = cls._box(r, 0.0, 0.20, 1.0, 0.80)
        p.setBrush(cls._grad(body, "#ffecb3", "#f9a825"))
        p.drawRoundedRect(body, cls._rad(r, 0.10), cls._rad(r, 0.10))
        # folder mouth highlight
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(255, 255, 255, 55)))
        p.drawRoundedRect(cls._box(r, 0.08, 0.32, 0.84, 0.22), 2, 2)

    @classmethod
    def _draw_save(cls, p, r, _s):
        cls._fill_round(p, r, "#64b5f6", "#1565c0", "#0d47a1", sheen=False)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#e3f2fd")))
        p.drawRect(cls._box(r, 0.22, 0.0, 0.56, 0.34))
        p.setBrush(QBrush(QColor("#fffde7")))
        p.drawRoundedRect(cls._box(r, 0.14, 0.46, 0.72, 0.48),
                          cls._rad(r, 0.06), cls._rad(r, 0.06))
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawRect(cls._box(r, 0.42, 0.0, 0.16, 0.18))

    @classmethod
    def _draw_new(cls, p, r, _s):
        sheet = cls._box(r, 0.12, 0.0, 0.76, 1.0)
        p.setPen(cls._pen("#1565c0", 1.2))
        p.setBrush(cls._grad(sheet, "#ffffff", "#e3f2fd"))
        p.drawRoundedRect(sheet, cls._rad(r, 0.08), cls._rad(r, 0.08))
        p.setPen(cls._pen("#2e7d32", 2.15))
        cx, cy = r.center().x(), r.center().y() + r.height() * 0.04
        s = r.width() * 0.22
        p.drawLine(QPointF(cx - s, cy), QPointF(cx + s, cy))
        p.drawLine(QPointF(cx, cy - s), QPointF(cx, cy + s))

    @classmethod
    def _draw_export(cls, p, r, _s):
        page = cls._box(r, 0.0, 0.08, 0.70, 0.84)
        p.setPen(cls._pen("#37474f", 1.2))
        p.setBrush(cls._grad(page, "#eceff1", "#b0bec5"))
        p.drawRoundedRect(page, cls._rad(r, 0.08), cls._rad(r, 0.08))
        p.setPen(cls._pen("#1565c0", 2.05))
        ax = r.left() + r.width() * 0.86
        p.drawLine(QPointF(ax, r.top() + r.height() * 0.08),
                   QPointF(ax, r.top() + r.height() * 0.78))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(cls._poly(r, [
            (0.86, 1.00), (0.68, 0.70), (1.00, 0.70),
        ]))

    @classmethod
    def _draw_paste(cls, p, r, _s):
        body = cls._box(r, 0.16, 0.26, 0.68, 0.74)
        p.setPen(cls._pen("#c47a00", 1.2))
        p.setBrush(cls._grad(body, "#ffe082", "#f9a825"))
        p.drawRoundedRect(body, cls._rad(r, 0.08), cls._rad(r, 0.08))
        clip = cls._box(r, 0.30, 0.0, 0.40, 0.34)
        p.setPen(cls._pen("#546e7a", 1.1))
        p.setBrush(cls._grad(clip, "#ffffff", "#cfd8dc"))
        p.drawRoundedRect(clip, cls._rad(r, 0.10), cls._rad(r, 0.10))

    @classmethod
    def _draw_copy(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        back = cls._box(r, 0.04, 0.28, 0.62, 0.68)
        p.setBrush(cls._grad(back, "#bbdefb", "#64b5f6"))
        p.drawRoundedRect(back, cls._rad(r, 0.08), cls._rad(r, 0.08))
        front = cls._box(r, 0.30, 0.04, 0.66, 0.68)
        p.setBrush(cls._grad(front, "#ffffff", "#e3f2fd"))
        p.drawRoundedRect(front, cls._rad(r, 0.08), cls._rad(r, 0.08))

    @classmethod
    def _draw_cut(cls, p, r, _s):
        p.setPen(cls._pen("#c55a11", 1.55))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cls._box(r, 0.00, 0.62, 0.34, 0.38))
        p.drawEllipse(cls._box(r, 0.66, 0.62, 0.34, 0.38))
        p.drawLine(cls._pt(r, 0.22, 0.70), cls._pt(r, 0.92, 0.06))
        p.drawLine(cls._pt(r, 0.78, 0.70), cls._pt(r, 0.08, 0.06))
        p.setPen(cls._pen("#c55a11", 1.15))
        p.drawLine(cls._pt(r, 0.28, 0.42), cls._pt(r, 0.72, 0.42))

    @classmethod
    def _draw_screenshot(cls, p, r, _s):
        cls._fill_round(p, r, "#cfd8dc", "#78909c", "#455a64", sheen=False)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#37474f")))
        p.drawRoundedRect(cls._box(r, 0.28, 0.10, 0.44, 0.22), 1.6, 1.6)
        p.setBrush(QBrush(QColor("#eceff1")))
        p.drawEllipse(cls._box(r, 0.22, 0.34, 0.56, 0.56))
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawEllipse(cls._box(r, 0.34, 0.46, 0.32, 0.32))

    @classmethod
    def _draw_undo(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.15))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        arc = r.adjusted(r.width() * 0.06, r.height() * 0.16,
                         -r.width() * 0.06, r.height() * 0.04)
        path.arcMoveTo(arc, 40)
        path.arcTo(arc, 40, 220)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(cls._poly(r, [
            (0.02, 0.48), (0.40, 0.22), (0.34, 0.68),
        ]))

    @classmethod
    def _draw_redo(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.15))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        arc = r.adjusted(r.width() * 0.06, r.height() * 0.16,
                         -r.width() * 0.06, r.height() * 0.04)
        path.arcMoveTo(arc, 140)
        path.arcTo(arc, 140, -220)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(cls._poly(r, [
            (0.98, 0.48), (0.60, 0.22), (0.66, 0.68),
        ]))

    @classmethod
    def _draw_delete(cls, p, r, _s):
        p.setPen(cls._pen("#b71c1c", 1.2))
        p.setBrush(QBrush(QColor("#c62828")))
        lid = cls._box(r, 0.08, 0.14, 0.84, 0.14)
        p.drawRoundedRect(lid, 1.2, 1.2)
        p.setBrush(cls._grad(r, "#ef9a9a", "#c62828"))
        p.drawRoundedRect(cls._box(r, 0.18, 0.28, 0.64, 0.70),
                          cls._rad(r, 0.08), cls._rad(r, 0.08))
        p.setPen(cls._pen("#ffffff", 1.35))
        for x in (0.38, 0.50, 0.62):
            p.drawLine(cls._pt(r, x, 0.40), cls._pt(r, x, 0.86))

    # -- settings / simulation --------------------------------------------

    @classmethod
    def _draw_units(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#bbdefb", "#1565c0")
        p.setFont(cls._font(r, 0.40))
        p.setPen(QPen(QColor("#0d47a1")))
        p.drawText(r, Qt.AlignCenter, "mm")

    @classmethod
    def _draw_setup(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0", sheen=False)
        p.setPen(cls._pen("#b71c1c", 1.1))
        p.setBrush(cls._grad(r, "#ef5350", "#c62828"))
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.28, 0.16))
        path.lineTo(cls._pt(r, 0.86, 0.50))
        path.lineTo(cls._pt(r, 0.28, 0.84))
        path.closeSubpath()
        p.drawPath(path)

    @classmethod
    def _draw_start(cls, p, r, _s):
        p.setPen(cls._pen("#1b5e20", 1.15))
        p.setBrush(cls._grad(r, "#81c784", "#2e7d32"))
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.18, 0.08))
        path.lineTo(cls._pt(r, 0.92, 0.50))
        path.lineTo(cls._pt(r, 0.18, 0.92))
        path.closeSubpath()
        p.drawPath(path)

    @classmethod
    def _draw_pause(cls, p, r, _s):
        p.setPen(cls._pen("#e65100", 1.1))
        p.setBrush(cls._grad(r, "#ffb74d", "#ef6c00"))
        w = 0.28
        p.drawRoundedRect(cls._box(r, 0.12, 0.06, w, 0.88), 2.2, 2.2)
        p.drawRoundedRect(cls._box(r, 0.60, 0.06, w, 0.88), 2.2, 2.2)

    @classmethod
    def _draw_stop(cls, p, r, _s):
        inner = cls._box(r, 0.08, 0.08, 0.84, 0.84)
        p.setPen(cls._pen("#b71c1c", 1.15))
        p.setBrush(cls._grad(inner, "#ef5350", "#c62828"))
        p.drawRoundedRect(inner, cls._rad(r, 0.10), cls._rad(r, 0.10))

    @classmethod
    def _draw_logfile(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0", sheen=False)
        p.setPen(cls._pen("#1565c0", 1.25))
        for i in range(4):
            y = 0.22 + i * 0.20
            p.drawLine(cls._pt(r, 0.16, y), cls._pt(r, 0.84, y))

    @classmethod
    def _draw_background(cls, p, r, _s):
        cls._fill_round(p, r, "#eceff1", "#b0bec5", "#78909c", sheen=False)
        g = QRadialGradient(cls._pt(r, 0.38, 0.36), r.width() * 0.55)
        g.setColorAt(0.0, QColor("#e3f2fd"))
        g.setColorAt(1.0, QColor("#1e88e5"))
        p.setPen(cls._pen("#1565c0", 1.1))
        p.setBrush(QBrush(g))
        p.drawEllipse(cls._box(r, 0.16, 0.16, 0.68, 0.68))

    @classmethod
    def _draw_frequency(cls, p, r, _s):
        p.setPen(cls._pen("#6a1b9a", 1.7))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.0, 0.50))
        steps = 24
        for i in range(1, steps + 1):
            x = i / steps
            y = 0.50 - 0.42 * math.sin(x * math.pi * 2.2)
            path.lineTo(cls._pt(r, x, y))
        p.drawPath(path)

    @classmethod
    def _draw_boundary(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.55))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r.adjusted(r.width() * 0.02, r.height() * 0.02,
                                     -r.width() * 0.02, -r.height() * 0.02),
                          cls._rad(r, 0.08), cls._rad(r, 0.08))
        p.setPen(cls._pen("#c62828", 1.45))
        p.drawLine(cls._pt(r, 0.14, 0.14), cls._pt(r, 0.86, 0.86))

    @classmethod
    def _draw_history(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.3))
        p.setBrush(cls._grad(r, "#ffffff", "#bbdefb"))
        p.drawEllipse(r)
        p.setPen(cls._pen("#c62828", 1.7))
        p.drawLine(cls._pt(r, 0.50, 0.50), cls._pt(r, 0.50, 0.16))
        p.drawLine(cls._pt(r, 0.50, 0.50), cls._pt(r, 0.82, 0.62))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#c62828")))
        p.drawEllipse(cls._box(r, 0.42, 0.42, 0.16, 0.16))

    @classmethod
    def _draw_optimizer(cls, p, r, _s):
        cls._fill_round(p, r, "#fff8e1", "#ffe0b2", "#ef6c00", sheen=False)
        p.setPen(cls._pen("#e65100", 1.7))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.10, 0.86))
        path.lineTo(cls._pt(r, 0.34, 0.52))
        path.lineTo(cls._pt(r, 0.58, 0.34))
        path.lineTo(cls._pt(r, 0.90, 0.12))
        p.drawPath(path)

    # -- tree / model ------------------------------------------------------

    @classmethod
    def _iso_cube(cls, p, box, light="#bbdefb", mid="#42a5f5", dark="#1565c0",
                  outline="#0d47a1"):
        """Isometric cube filling `box` (CST Navigation Tree solid)."""
        p.setPen(cls._pen(outline, 1.05))
        front = QRectF(box.left(), box.top() + box.height() * 0.28,
                       box.width() * 0.72, box.height() * 0.72)
        p.setBrush(cls._grad(front, mid, dark))
        p.drawRect(front)
        p.setBrush(cls._grad(box, light, mid))
        p.drawPolygon(QPolygonF([
            QPointF(front.left(), front.top()),
            QPointF(front.left() + box.width() * 0.28, box.top()),
            QPointF(box.right(), box.top()),
            QPointF(front.right(), front.top()),
        ]))
        p.setBrush(cls._grad(box, mid, dark, vertical=False))
        p.drawPolygon(QPolygonF([
            QPointF(front.right(), front.top()),
            QPointF(box.right(), box.top()),
            QPointF(box.right(), box.bottom() - box.height() * 0.18),
            QPointF(front.right(), front.bottom()),
        ]))

    @classmethod
    def _draw_collection(cls, p, r, _s):
        """Cluster of three cubes — CST folder / Components root."""
        cls._iso_cube(p, cls._box(r, 0.00, 0.10, 0.50, 0.58),
                      "#e3f2fd", "#90caf9", "#42a5f5")
        cls._iso_cube(p, cls._box(r, 0.42, 0.00, 0.50, 0.58),
                      "#bbdefb", "#64b5f6", "#1e88e5")
        cls._iso_cube(p, cls._box(r, 0.18, 0.32, 0.64, 0.68),
                      "#bbdefb", "#42a5f5", "#1565c0")

    @classmethod
    def _draw_solid(cls, p, r, _s):
        """Single isometric cube — CST body / solid leaf."""
        cls._iso_cube(p, r, "#cfe8fc", "#64b5f6", "#1e88e5")

    @classmethod
    def _draw_component(cls, p, r, _s):
        cls._draw_solid(p, r, _s)

    @classmethod
    def _draw_solid_excluded(cls, p, r, _s):
        cls._draw_solid(p, r, _s)
        badge = cls._box(r, -0.02, 0.48, 0.52, 0.52)
        p.setPen(cls._pen("#b71c1c", 1.05))
        p.setBrush(QBrush(QColor("#e53935")))
        p.drawEllipse(badge)
        p.setPen(cls._pen("#ffffff", 1.7))
        cy = badge.center().y()
        p.drawLine(QPointF(badge.left() + badge.width() * 0.22, cy),
                   QPointF(badge.right() - badge.width() * 0.22, cy))

    @classmethod
    def _draw_folder(cls, p, r, _s):
        p.setPen(cls._pen("#8d6e63", 1.1))
        tab = cls._box(r, 0.00, 0.08, 0.46, 0.28)
        p.setBrush(cls._grad(tab, "#ffe0b2", "#ffcc80"))
        p.drawRoundedRect(tab, 1.4, 1.4)
        body = cls._box(r, 0.00, 0.22, 1.00, 0.78)
        p.setBrush(cls._grad(body, "#ffe0b2", "#d7ccc8"))
        p.drawRoundedRect(body, 1.8, 1.8)

    @classmethod
    def _draw_meshgroup(cls, p, r, _s):
        colors = [("#42a5f5", "#1565c0"), ("#66bb6a", "#2e7d32"),
                  ("#ffee58", "#f9a825"), ("#ff9800", "#ef6c00")]
        p.setPen(cls._pen("#455a64", 0.95))
        for i, (c1, c2) in enumerate(colors):
            cell = cls._box(r, 0.04 + (i % 2) * 0.48, 0.04 + (i // 2) * 0.48,
                            0.44, 0.44)
            p.setBrush(cls._grad(cell, c1, c2))
            p.drawRect(cell)

    @classmethod
    def _draw_meshitem(cls, p, r, _s):
        colors = [("#42a5f5", "#1565c0"), ("#66bb6a", "#2e7d32"),
                  ("#ffee58", "#f9a825"), ("#ff9800", "#ef6c00")]
        p.setPen(cls._pen("#455a64", 0.9))
        for i, (c1, c2) in enumerate(colors):
            cell = cls._box(r, 0.00 + (i % 2) * 0.28, 0.22 + (i // 2) * 0.28,
                            0.26, 0.26)
            p.setBrush(cls._grad(cell, c1, c2))
            p.drawRect(cell)
        cls._iso_cube(p, cls._box(r, 0.40, 0.18, 0.60, 0.78),
                      "#bbdefb", "#42a5f5", "#1565c0")

    @classmethod
    def _draw_gear(cls, p, r, _s):
        cx, cy = r.center().x(), r.center().y()
        outer = min(r.width(), r.height()) * 0.46
        inner = outer * 0.42
        hole = outer * 0.22
        path = QPainterPath()
        teeth = 8
        for i in range(teeth * 2):
            ang = math.radians(-90 + i * 180.0 / teeth)
            rad = outer if i % 2 == 0 else inner * 1.08
            pt = QPointF(cx + rad * math.cos(ang), cy + rad * math.sin(ang))
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        path.closeSubpath()
        p.setPen(cls._pen("#546e7a", 1.05))
        p.setBrush(cls._grad(r, "#cfd8dc", "#78909c"))
        p.drawPath(path)
        p.setBrush(QBrush(QColor("#eceef1")))
        p.drawEllipse(QPointF(cx, cy), hole, hole)

    @classmethod
    def _draw_results(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0", sheen=False)
        p.setPen(cls._pen("#1565c0", 1.55))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.12, 0.78))
        path.lineTo(cls._pt(r, 0.32, 0.42))
        path.lineTo(cls._pt(r, 0.48, 0.58))
        path.lineTo(cls._pt(r, 0.68, 0.22))
        path.lineTo(cls._pt(r, 0.88, 0.36))
        p.drawPath(path)

    @classmethod
    def _paint_mat_sphere(cls, p, r, rgb):
        r0, g0, b0 = rgb
        light = QColor(min(255, r0 + 70), min(255, g0 + 70), min(255, b0 + 70))
        mid = QColor(r0, g0, b0)
        dark = QColor(max(0, r0 - 50), max(0, g0 - 50), max(0, b0 - 50))
        g = QRadialGradient(cls._pt(r, 0.34, 0.30), r.width() * 0.78)
        g.setColorAt(0.0, light)
        g.setColorAt(0.45, mid)
        g.setColorAt(1.0, dark)
        p.setPen(cls._pen(dark.name(), 1.1))
        p.setBrush(QBrush(g))
        p.drawEllipse(r)

    @classmethod
    def _draw_group(cls, p, r, _s):
        cls._draw_collection(p, r, _s)

    @classmethod
    def _draw_material(cls, p, r, _s):
        cls._paint_mat_sphere(p, r, (80, 170, 190))

    @classmethod
    def _draw_faces(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        p.setBrush(cls._grad(r, "#e3f2fd", "#64b5f6"))
        p.drawPolygon(cls._poly(r, [
            (0.08, 0.78), (0.88, 0.78), (0.96, 0.18), (0.04, 0.18),
        ]))

    @classmethod
    def _draw_curves(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.85))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.04, 0.90))
        path.cubicTo(cls._pt(r, 0.28, 0.04),
                     cls._pt(r, 0.72, 0.96),
                     cls._pt(r, 0.96, 0.10))
        p.drawPath(path)

    @classmethod
    def _draw_wcs(cls, p, r, _s):
        p.setPen(cls._pen("#c62828", 2.0))
        p.drawLine(cls._pt(r, 0.50, 0.50), cls._pt(r, 1.00, 0.50))
        p.setPen(cls._pen("#2e7d32", 2.0))
        p.drawLine(cls._pt(r, 0.50, 0.50), cls._pt(r, 0.50, 0.00))
        p.setPen(cls._pen("#1565c0", 2.0))
        p.drawLine(cls._pt(r, 0.50, 0.50), cls._pt(r, 0.04, 0.96))

    @classmethod
    def _draw_anchor(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.55))
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawEllipse(cls._box(r, 0.34, 0.34, 0.32, 0.32))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cls._box(r, 0.12, 0.12, 0.76, 0.76))

    @classmethod
    def _draw_wires(cls, p, r, _s):
        p.setPen(cls._pen("#e65100", 1.7))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.08, 0.96))
        path.lineTo(cls._pt(r, 0.08, 0.08))
        path.lineTo(cls._pt(r, 0.92, 0.08))
        path.lineTo(cls._pt(r, 0.92, 0.96))
        p.drawPath(path)

    @classmethod
    def _draw_dimensions(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.45))
        p.setBrush(Qt.NoBrush)
        p.drawLine(cls._pt(r, 0.08, 0.92), cls._pt(r, 0.92, 0.92))
        p.drawLine(cls._pt(r, 0.08, 0.08), cls._pt(r, 0.08, 0.92))
        p.setPen(cls._pen("#c62828", 1.2))
        p.drawLine(cls._pt(r, 0.08, 0.08), cls._pt(r, 0.18, 0.18))
        p.drawLine(cls._pt(r, 0.92, 0.92), cls._pt(r, 0.82, 0.82))

    @classmethod
    def _draw_lumped(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.45))
        p.setBrush(Qt.NoBrush)
        p.drawLine(cls._pt(r, 0.0, 0.50), cls._pt(r, 1.0, 0.50))
        for x in (0.22, 0.40, 0.58, 0.76):
            p.drawLine(cls._pt(r, x, 0.22), cls._pt(r, x, 0.78))

    @classmethod
    def _draw_ports(cls, p, r, _s):
        p.setPen(cls._pen("#e65100", 1.3))
        p.setBrush(cls._grad(r, "#ffe0b2", "#ef6c00"))
        p.drawEllipse(r)
        p.setPen(cls._pen("#bf360c", 1.45))
        p.drawLine(cls._pt(r, 0.50, 0.10), cls._pt(r, 0.50, 0.90))
        p.drawLine(cls._pt(r, 0.18, 0.50), cls._pt(r, 0.82, 0.50))

    @classmethod
    def _draw_sources(cls, p, r, _s):
        p.setPen(cls._pen("#b71c1c", 1.2))
        p.setBrush(cls._grad(r, "#ef5350", "#c62828"))
        p.drawEllipse(cls._box(r, 0.06, 0.06, 0.88, 0.88))
        p.setPen(QPen(QColor("#fff")))
        p.setFont(cls._font(r, 0.52))
        p.drawText(r, Qt.AlignCenter, "~")

    @classmethod
    def _draw_monitor(cls, p, r, _s):
        cls._fill_round(p, r, "#e3f2fd", "#64b5f6", "#1565c0")
        p.setFont(cls._font(r, 0.50))
        p.setPen(QPen(QColor("#0d47a1")))
        p.drawText(r, Qt.AlignCenter, "M")

    @classmethod
    def _draw_voltage(cls, p, r, _s):
        p.setPen(cls._pen("#e65100", 1.55))
        p.setBrush(Qt.NoBrush)
        p.drawLine(cls._pt(r, 0.12, 0.92), cls._pt(r, 0.12, 0.08))
        p.drawLine(cls._pt(r, 0.88, 0.92), cls._pt(r, 0.88, 0.08))
        p.drawLine(cls._pt(r, 0.12, 0.50), cls._pt(r, 0.88, 0.50))

    @classmethod
    def _draw_probe(cls, p, r, _s):
        p.setPen(cls._pen("#e65100", 1.25))
        p.setBrush(cls._grad(r, "#ffcc80", "#ef6c00"))
        p.drawEllipse(cls._box(r, 0.08, 0.08, 0.84, 0.84))
        p.setPen(QPen(QColor("#fff")))
        p.setFont(cls._font(r, 0.48))
        p.drawText(r, Qt.AlignCenter, "?")

    @classmethod
    def _draw_mesh(cls, p, r, _s):
        cls._fill_round(p, r, "#e0f7fa", "#4dd0e1", "#00838f", sheen=False)
        p.setPen(cls._pen("#006064", 1.05))
        for i in range(1, 4):
            y = i / 4.0
            p.drawLine(cls._pt(r, 0.06, y), cls._pt(r, 0.94, y))
        for j in range(1, 4):
            x = j / 4.0
            p.drawLine(cls._pt(r, x, 0.06), cls._pt(r, x, 0.94))

    @classmethod
    def _draw_1d(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        p.drawLine(cls._pt(r, 0.06, 0.92), cls._pt(r, 0.94, 0.92))
        p.drawLine(cls._pt(r, 0.06, 0.08), cls._pt(r, 0.06, 0.92))
        p.setPen(cls._pen("#c62828", 1.7))
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.10, 0.86))
        path.lineTo(cls._pt(r, 0.32, 0.28))
        path.lineTo(cls._pt(r, 0.52, 0.18))
        path.lineTo(cls._pt(r, 0.72, 0.62))
        path.lineTo(cls._pt(r, 0.94, 0.14))
        p.drawPath(path)

    @classmethod
    def _draw_2d(cls, p, r, _s):
        cls._fill_round(p, r, "#e3f2fd", "#90caf9", "#1565c0", sheen=False)
        p.setPen(cls._pen("#c62828", 1.35))
        p.drawLine(cls._pt(r, 0.12, 0.78), cls._pt(r, 0.88, 0.22))
        p.drawLine(cls._pt(r, 0.12, 0.22), cls._pt(r, 0.88, 0.78))

    @classmethod
    def _draw_farfield(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.35))
        p.setBrush(QBrush(QColor(33, 150, 243, 40)))
        cx, cy = r.center().x(), r.center().y()
        path = QPainterPath()
        first = True
        for a in range(0, 361, 6):
            rad = math.radians(a)
            rr = r.width() * 0.46 * (0.50 + 0.50 * abs(math.cos(3 * rad)))
            pt = QPointF(cx + rr * math.cos(rad), cy + rr * math.sin(rad))
            if first:
                path.moveTo(pt)
                first = False
            else:
                path.lineTo(pt)
        path.closeSubpath()
        p.drawPath(path)

    @classmethod
    def _draw_tables(cls, p, r, _s):
        cls._fill_round(p, r, "#e3f2fd", "#90caf9", "#1565c0", sheen=False)
        p.setPen(cls._pen("#1565c0", 1.05))
        for i in range(1, 3):
            p.drawLine(cls._pt(r, 0.08, i / 3.0), cls._pt(r, 0.92, i / 3.0))
        p.drawLine(cls._pt(r, 0.50, 0.08), cls._pt(r, 0.50, 0.92))

    @classmethod
    def _draw_codebook(cls, p, r, _s):
        cls._fill_round(p, r, "#fff8e1", "#ffe082", "#f9a825", sheen=False)
        p.setPen(cls._pen("#e65100", 1.2))
        for i in range(4):
            y = 0.22 + i * 0.20
            p.drawLine(cls._pt(r, 0.16, y), cls._pt(r, 0.84, y))

    # -- primitives / boolean / transform ---------------------------------

    @classmethod
    def _draw_brick(cls, p, r, _s):
        p.setPen(cls._pen("#0d47a1", 1.15))
        front = cls._box(r, 0.0, 0.28, 0.72, 0.72)
        p.setBrush(cls._grad(front, "#90caf9", "#1565c0"))
        p.drawRect(front)
        p.setBrush(cls._grad(r, "#e3f2fd", "#64b5f6"))
        p.drawPolygon(cls._poly(r, [
            (0.00, 0.28), (0.28, 0.00), (1.00, 0.00), (0.72, 0.28),
        ]))
        p.setBrush(cls._grad(r, "#64b5f6", "#0d47a1", vertical=False))
        p.drawPolygon(cls._poly(r, [
            (0.72, 0.28), (1.00, 0.00), (1.00, 0.72), (0.72, 1.00),
        ]))

    @classmethod
    def _draw_cylinder(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.15))
        p.setBrush(cls._grad(r, "#90caf9", "#1565c0", vertical=False))
        p.drawRect(cls._box(r, 0.08, 0.16, 0.84, 0.68))
        p.setBrush(cls._grad(r, "#bbdefb", "#64b5f6"))
        p.drawEllipse(cls._box(r, 0.08, 0.00, 0.84, 0.32))
        p.setBrush(cls._grad(r, "#e3f2fd", "#90caf9"))
        p.drawEllipse(cls._box(r, 0.08, 0.68, 0.84, 0.32))

    @classmethod
    def _draw_sphere(cls, p, r, _s):
        g = QRadialGradient(cls._pt(r, 0.34, 0.30), r.width() * 0.78)
        g.setColorAt(0.0, QColor("#e3f2fd"))
        g.setColorAt(0.55, QColor("#42a5f5"))
        g.setColorAt(1.0, QColor("#0d47a1"))
        p.setPen(cls._pen("#0d47a1", 1.15))
        p.setBrush(QBrush(g))
        p.drawEllipse(r)
        p.setPen(cls._pen("#1565c0", 0.95))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cls._box(r, 0.04, 0.36, 0.92, 0.28))

    @classmethod
    def _draw_torus(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cls._box(r, 0.02, 0.10, 0.96, 0.80))
        p.setPen(cls._pen("#1565c0", 1.55))
        p.drawEllipse(cls._box(r, 0.28, 0.32, 0.44, 0.36))

    @classmethod
    def _draw_cone(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.15))
        p.setBrush(cls._grad(r, "#90caf9", "#1565c0"))
        p.drawPolygon(cls._poly(r, [
            (0.50, 0.00), (0.96, 0.78), (0.04, 0.78),
        ]))
        p.setBrush(cls._grad(r, "#e3f2fd", "#64b5f6"))
        p.drawEllipse(cls._box(r, 0.04, 0.68, 0.92, 0.32))

    @classmethod
    def _draw_union(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.15))
        p.setBrush(QBrush(QColor(144, 202, 249, 210)))
        p.drawEllipse(cls._box(r, 0.00, 0.04, 0.72, 0.72))
        p.setBrush(QBrush(QColor(33, 150, 243, 200)))
        p.drawEllipse(cls._box(r, 0.28, 0.24, 0.72, 0.72))

    @classmethod
    def _draw_subtract(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.15))
        p.setBrush(cls._grad(r, "#90caf9", "#1565c0"))
        p.drawRoundedRect(cls._box(r, 0.0, 0.08, 0.78, 0.84),
                          cls._rad(r, 0.08), cls._rad(r, 0.08))
        p.setPen(cls._pen("#c62828", 1.2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(cls._box(r, 0.38, 0.16, 0.62, 0.68))

    @classmethod
    def _draw_intersect(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.25))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(cls._box(r, 0.00, 0.04, 0.72, 0.72))
        p.drawEllipse(cls._box(r, 0.28, 0.24, 0.72, 0.72))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawEllipse(cls._box(r, 0.32, 0.32, 0.36, 0.36))

    @classmethod
    def _draw_translate(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawLine(cls._pt(r, 0.04, 0.50), cls._pt(r, 0.72, 0.50))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(cls._poly(r, [
            (1.00, 0.50), (0.64, 0.22), (0.64, 0.78),
        ]))

    @classmethod
    def _draw_rotate(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 2.0))
        p.setBrush(Qt.NoBrush)
        p.drawArc(r.toRect(), 40 * 16, 280 * 16)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#1565c0")))
        p.drawPolygon(cls._poly(r, [
            (0.96, 0.42), (0.62, 0.12), (0.72, 0.58),
        ]))

    @classmethod
    def _draw_front(cls, p, r, _s):
        cls._fill_round(p, r, "#bbdefb", "#1e88e5", "#1565c0")
        p.setFont(cls._font(r, 0.52))
        p.setPen(QPen(QColor("#0d47a1")))
        p.drawText(r, Qt.AlignCenter, "F")

    @classmethod
    def _draw_top(cls, p, r, _s):
        cls._fill_round(p, r, "#c8e6c9", "#43a047", "#2e7d32")
        p.setFont(cls._font(r, 0.52))
        p.setPen(QPen(QColor("#1b5e20")))
        p.drawText(r, Qt.AlignCenter, "T")

    @classmethod
    def _draw_side(cls, p, r, _s):
        cls._fill_round(p, r, "#ffcdd2", "#e53935", "#c62828")
        p.setFont(cls._font(r, 0.52))
        p.setPen(QPen(QColor("#b71c1c")))
        p.drawText(r, Qt.AlignCenter, "S")

    @classmethod
    def _draw_mirror(cls, p, r, _s):
        p.setPen(cls._pen("#90a4ae", 1.35))
        p.drawLine(cls._pt(r, 0.50, 0.00), cls._pt(r, 0.50, 1.00))
        p.setPen(cls._pen("#1565c0", 1.15))
        p.setBrush(cls._grad(r, "#90caf9", "#1565c0"))
        p.drawPolygon(cls._poly(r, [
            (0.04, 0.92), (0.04, 0.12), (0.42, 0.50),
        ]))
        p.setBrush(cls._grad(r, "#bbdefb", "#64b5f6"))
        p.drawPolygon(cls._poly(r, [
            (0.96, 0.92), (0.96, 0.12), (0.58, 0.50),
        ]))

    @classmethod
    def _draw_scale(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.15))
        small = cls._box(r, 0.0, 0.42, 0.46, 0.50)
        p.setBrush(cls._grad(small, "#bbdefb", "#64b5f6"))
        p.drawRoundedRect(small, 1.6, 1.6)
        big = cls._box(r, 0.28, 0.0, 0.72, 0.72)
        p.setBrush(cls._grad(big, "#64b5f6", "#1565c0"))
        p.drawRoundedRect(big, 2.0, 2.0)

    # -- view --------------------------------------------------------------

    @classmethod
    def _draw_fit(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.85))
        p.setBrush(Qt.NoBrush)
        s = 0.30
        for x, y, sx, sy in (
                (0.0, 0.0, 1, 1), (1.0, 0.0, -1, 1),
                (0.0, 1.0, 1, -1), (1.0, 1.0, -1, -1),
        ):
            p.drawLine(cls._pt(r, x, y), cls._pt(r, x + sx * s, y))
            p.drawLine(cls._pt(r, x, y), cls._pt(r, x, y + sy * s))

    @classmethod
    def _draw_zoom(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.7))
        p.setBrush(cls._grad(r, "#ffffff", "#e3f2fd"))
        p.drawEllipse(cls._box(r, 0.02, 0.02, 0.68, 0.68))
        p.setPen(cls._pen("#1565c0", 2.15))
        p.drawLine(cls._pt(r, 0.58, 0.58), cls._pt(r, 0.96, 0.96))
        p.setPen(cls._pen("#1565c0", 1.55))
        p.drawLine(cls._pt(r, 0.18, 0.36), cls._pt(r, 0.50, 0.36))
        p.drawLine(cls._pt(r, 0.34, 0.20), cls._pt(r, 0.34, 0.52))

    @classmethod
    def _draw_perspective(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.15))
        p.setBrush(cls._grad(r, "#bbdefb", "#1e88e5"))
        p.drawPolygon(cls._poly(r, [
            (0.12, 0.96), (0.32, 0.08), (0.82, 0.08), (1.00, 0.96),
        ]))

    @classmethod
    def _draw_wireframe(cls, p, r, _s):
        p.setPen(cls._pen("#37474f", 1.25))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(cls._poly(r, [
            (0.04, 0.28), (0.68, 0.28), (0.68, 1.00), (0.04, 1.00),
        ]))
        p.drawLine(cls._pt(r, 0.04, 0.28), cls._pt(r, 0.32, 0.00))
        p.drawLine(cls._pt(r, 0.68, 0.28), cls._pt(r, 0.96, 0.00))
        p.drawLine(cls._pt(r, 0.68, 1.00), cls._pt(r, 0.96, 0.72))
        p.drawLine(cls._pt(r, 0.32, 0.00), cls._pt(r, 0.96, 0.00))
        p.drawLine(cls._pt(r, 0.96, 0.00), cls._pt(r, 0.96, 0.72))

    @classmethod
    def _draw_bounding(cls, p, r, _s):
        p.setPen(cls._pen("#9e9e9e", 1.25))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r)
        p.setPen(cls._pen("#1565c0", 1.25))
        p.drawRect(cls._box(r, 0.16, 0.16, 0.68, 0.68))

    # -- misc --------------------------------------------------------------

    @classmethod
    def _draw_editprops(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0", sheen=False)
        p.setPen(cls._pen("#1565c0", 1.2))
        for i in range(3):
            y = 0.26 + i * 0.24
            p.drawLine(cls._pt(r, 0.16, y), cls._pt(r, 0.84, y))

    @classmethod
    def _draw_list(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0", sheen=False)
        p.setPen(cls._pen("#e65100", 1.45))
        for i in range(4):
            y = 0.20 + i * 0.20
            p.drawLine(cls._pt(r, 0.14, y), cls._pt(r, 0.42, y))
        p.setPen(cls._pen("#90a4ae", 1.1))
        for i in range(4):
            y = 0.20 + i * 0.20
            p.drawLine(cls._pt(r, 0.48, y), cls._pt(r, 0.86, y))

    @classmethod
    def _draw_calculator(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0")
        p.setPen(QPen(QColor("#c62828")))
        p.setFont(cls._font(r, 0.34))
        p.drawText(r, Qt.AlignCenter, "f(x)")

    @classmethod
    def _draw_parametric(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0")
        p.setPen(QPen(QColor("#c62828")))
        p.setFont(cls._font(r, 0.52))
        p.drawText(r, Qt.AlignCenter, "\u03bb")

    @classmethod
    def _draw_macros(cls, p, r, _s):
        cls._fill_round(p, r, "#fff3e0", "#ffcc80", "#ef6c00")
        p.setPen(QPen(QColor("#e65100")))
        p.setFont(cls._font(r, 0.32))
        p.drawText(r, Qt.AlignCenter, "VBA")

    @classmethod
    def _draw_python(cls, p, r, _s):
        cls._fill_round(p, r, "#e3f2fd", "#64b5f6", "#1565c0")
        p.setPen(QPen(QColor("#0d47a1")))
        p.setFont(cls._font(r, 0.38))
        p.drawText(r, Qt.AlignCenter, "Py")

    @classmethod
    def _draw_report(cls, p, r, _s):
        cls._fill_round(p, r, "#ffffff", "#e3f2fd", "#1565c0")
        p.setPen(QPen(QColor("#c62828")))
        p.setFont(cls._font(r, 0.50))
        p.drawText(r, Qt.AlignCenter, "R")

    @classmethod
    def _draw_help(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        p.setBrush(cls._grad(r, "#fff8e1", "#ffecb3"))
        p.drawEllipse(r)
        p.setPen(QPen(QColor("#c62828")))
        p.setFont(cls._font(r, 0.52))
        p.drawText(r, Qt.AlignCenter, "?")

    @classmethod
    def _draw_field(cls, p, r, _s):
        p.setPen(cls._pen("#6a1b9a", 1.45))
        p.setBrush(Qt.NoBrush)
        for i in range(3):
            path = QPainterPath()
            y0 = 0.22 + i * 0.28
            path.moveTo(cls._pt(r, 0.0, y0))
            for k in range(1, 21):
                x = k / 20.0
                y = y0 + 0.12 * math.sin(x * math.pi * 3 + i)
                path.lineTo(cls._pt(r, x, y))
            p.drawPath(path)

    @classmethod
    def _draw_show(cls, p, r, _s):
        p.setPen(cls._pen("#1565c0", 1.2))
        p.setBrush(cls._grad(r, "#e3f2fd", "#90caf9"))
        path = QPainterPath()
        path.moveTo(cls._pt(r, 0.04, 0.50))
        path.quadTo(cls._pt(r, 0.50, 0.06), cls._pt(r, 0.96, 0.50))
        path.quadTo(cls._pt(r, 0.50, 0.94), cls._pt(r, 0.04, 0.50))
        p.drawPath(path)
        p.setBrush(QBrush(QColor("#0d47a1")))
        p.drawEllipse(cls._box(r, 0.36, 0.36, 0.28, 0.28))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(cls._box(r, 0.44, 0.40, 0.10, 0.10))

    @classmethod
    def _draw_hide(cls, p, r, _s):
        cls._draw_show(p, r, _s)
        p.setPen(cls._pen("#c62828", 2.05))
        p.drawLine(cls._pt(r, 0.10, 0.90), cls._pt(r, 0.90, 0.10))

    @classmethod
    def _draw_select_rect(cls, p, r, _s):
        pen = cls._pen("#1565c0", 1.15)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(QBrush(QColor(21, 101, 192, 28)))
        p.drawRect(cls._box(r, 0.20, 0.24, 0.68, 0.56))
        p.setPen(cls._pen("#c62828", 1.25))
        p.drawLine(cls._pt(r, 0.06, 0.50), cls._pt(r, 0.94, 0.50))
        p.drawLine(cls._pt(r, 0.50, 0.06), cls._pt(r, 0.50, 0.94))

    @classmethod
    def _draw_info(cls, p, r, _s):
        p.setPen(cls._pen("#0d47a1", 1.15))
        p.setBrush(cls._grad(r, "#64b5f6", "#1565c0"))
        p.drawEllipse(r)
        p.setPen(QPen(QColor("#ffffff")))
        p.setFont(cls._font(r, 0.58))
        p.drawText(r, Qt.AlignCenter, "i")

    @classmethod
    def _draw_rename(cls, p, r, _s):
        card = cls._box(r, 0.04, 0.18, 0.72, 0.70)
        p.setPen(cls._pen("#1565c0", 1.1))
        p.setBrush(cls._grad(card, "#ffffff", "#e3f2fd"))
        p.drawRoundedRect(card, cls._rad(r, 0.08), cls._rad(r, 0.08))
        p.setPen(QPen(QColor("#1565c0")))
        p.setFont(cls._font(r, 0.28))
        p.drawText(card, Qt.AlignCenter, "Abc")
        p.setPen(cls._pen("#ef6c00", 1.35))
        p.drawLine(cls._pt(r, 0.58, 0.86), cls._pt(r, 0.90, 0.28))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#ef6c00")))
        p.drawPolygon(cls._poly(r, [(0.90, 0.20), (0.98, 0.36), (0.82, 0.34)]))

    @classmethod
    def _draw_slice(cls, p, r, _s):
        p.setPen(cls._pen("#546e7a", 1.15))
        p.setBrush(cls._grad(r, "#eceff1", "#90a4ae"))
        p.drawPolygon(cls._poly(r, [
            (0.18, 0.22), (0.82, 0.22), (0.82, 0.78), (0.18, 0.78),
        ]))
        p.setPen(cls._pen("#1565c0", 1.35))
        p.setBrush(QBrush(QColor(21, 101, 192, 80)))
        p.drawPolygon(cls._poly(r, [
            (0.04, 0.62), (0.96, 0.28), (0.96, 0.42), (0.04, 0.76),
        ]))

    @classmethod
    def _draw_align(cls, p, r, _s):
        p.setPen(cls._pen("#455a64", 1.15))
        p.setBrush(cls._grad(r, "#cfd8dc", "#78909c"))
        p.drawRoundedRect(cls._box(r, 0.08, 0.72, 0.84, 0.22),
                          cls._rad(r, 0.06), cls._rad(r, 0.06))
        p.setPen(cls._pen("#0d47a1", 1.15))
        p.setBrush(cls._grad(r, "#90caf9", "#1565c0"))
        p.drawEllipse(cls._box(r, 0.28, 0.08, 0.44, 0.44))
        p.drawRoundedRect(cls._box(r, 0.30, 0.28, 0.40, 0.48),
                          cls._rad(r, 0.10), cls._rad(r, 0.10))
