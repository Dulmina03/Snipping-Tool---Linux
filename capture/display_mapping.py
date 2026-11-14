"""Frozen GNOME stage-to-PNG geometry; no screen capture or display changes."""
import asyncio
from dataclasses import dataclass
import math

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus


class DisplayMappingError(RuntimeError):
    pass


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self):
        return self.x + self.width

    @property
    def bottom(self):
        return self.y + self.height

    def intersect(self, other):
        x, y = max(self.x, other.x), max(self.y, other.y)
        return Rect(x, y, max(0, min(self.right, other.right) - x),
                    max(0, min(self.bottom, other.bottom) - y))


def bounds(rects):
    if not rects:
        raise DisplayMappingError('No active display geometry is available.')
    x, y = min(r.x for r in rects), min(r.y for r in rects)
    return Rect(x, y, max(r.right for r in rects) - x, max(r.bottom for r in rects) - y)


def covered(rect, monitors):
    """Reject gaps/outside pixels; do not silently manufacture black padding."""
    pieces = [rect.intersect(m) for m in monitors]
    xs = sorted({rect.x, rect.right, *(p.x for p in pieces), *(p.right for p in pieces)})
    area = 0
    for left, right in zip(xs, xs[1:]):
        spans = sorted((p.y, p.bottom) for p in pieces
                       if p.width > 0 and p.height > 0 and p.x <= left and p.right >= right)
        end = rect.y
        for top, bottom in spans:
            start = max(top, end)
            area += (right - left) * max(0, bottom - start)
            end = max(end, bottom)
    return math.isclose(area, rect.width * rect.height, rel_tol=0, abs_tol=1e-6)


@dataclass(frozen=True)
class Monitor:
    name: str
    logical: Rect  # GNOME compositor coordinates, independent of Qt DPR
    scale: float
    primary: bool = False


@dataclass(frozen=True)
class Layout:
    serial: int
    monitors: tuple[Monitor, ...]
    mode: int = 1

    @property
    def desktop(self):
        return bounds([monitor.logical for monitor in self.monitors])

    def mapping(self, image_size, software='gnome-screenshot'):
        if self.mode != 1:
            raise DisplayMappingError('Rectangle capture cannot verify GNOME physical-layout mode. Use Window or Full Screen.')
        if software != 'gnome-screenshot':
            raise DisplayMappingError('Rectangle capture cannot identify the portal image layout. Use Window or Full Screen.')
        desktop = self.desktop
        if desktop.width <= 0 or desktop.height <= 0:
            raise DisplayMappingError('Invalid desktop bounds.')
        # GNOME Shell captures the whole stage at the maximum stage-view scale.
        # Fractional scaling may use ceil(scale) render buffers. Validate the
        # observed PNG against those contracts, never against each Qt DPR.
        maximum = max(1., *(monitor.scale for monitor in self.monitors))
        candidates = {maximum, float(math.ceil(maximum))}
        scales = [s for s in candidates if (math.floor(desktop.width * s + .5),
                  math.floor(desktop.height * s + .5)) == tuple(image_size)]
        if len(scales) != 1:
            raise DisplayMappingError('Portal image dimensions do not match the frozen GNOME desktop. Use Window or Full Screen.')
        return CaptureMapping(self, tuple(image_size), scales[0])


@dataclass(frozen=True)
class CaptureMapping:
    layout: Layout
    image_size: tuple[int, int]
    scale: float

    def crop_box(self, canvas_rect):
        """Canvas coordinates start at desktop bounds; PNG uses half-open edges."""
        desktop = self.layout.desktop
        rect = Rect(canvas_rect.x + desktop.x, canvas_rect.y + desktop.y,
                    canvas_rect.width, canvas_rect.height)
        if not all(math.isfinite(v) for v in (rect.x, rect.y, rect.width, rect.height)):
            raise DisplayMappingError('Invalid selection coordinates.')
        if rect.width <= 0 or rect.height <= 0:
            raise DisplayMappingError('The selection is empty.')
        rect = rect.intersect(desktop)
        if rect.width <= 0 or rect.height <= 0 or not covered(rect, [m.logical for m in self.layout.monitors]):
            raise DisplayMappingError('Selection includes space outside the displays. Select an area covered by monitors.')
        x, y = rect.x - desktop.x, rect.y - desktop.y
        left = max(0, math.floor(x * self.scale + 1e-8))
        top = max(0, math.floor(y * self.scale + 1e-8))
        right = min(self.image_size[0], math.ceil((x + rect.width) * self.scale - 1e-8))
        bottom = min(self.image_size[1], math.ceil((y + rect.height) * self.scale - 1e-8))
        if right <= left or bottom <= top:
            raise DisplayMappingError('The selection contains no screenshot pixels.')
        return left, top, right, bottom

    def source_rect(self, monitor):
        desktop = self.layout.desktop
        rect = monitor.logical
        return Rect((rect.x - desktop.x) * self.scale, (rect.y - desktop.y) * self.scale,
                    rect.width * self.scale, rect.height * self.scale)


def value(item):
    return getattr(item, 'value', item)


def parse_layout(body):
    serial, physical, logical, properties = body
    mode = value(properties.get('layout-mode', 0))
    current = {}
    for spec, modes, _ in physical:
        selected = [entry for entry in modes if value(entry[6].get('is-current', False))]
        if len(selected) == 1:
            current[spec[0]] = (selected[0][1], selected[0][2])
    monitors = []
    for x, y, scale, transform, primary, specs, _ in logical:
        if len(specs) != 1 or specs[0][0] not in current:
            raise DisplayMappingError('Cloned or unidentified monitors cannot be mapped reliably. Use Window or Full Screen.')
        name = specs[0][0]
        width, height = current[name]
        if not math.isfinite(scale) or scale <= 0:
            raise DisplayMappingError('Invalid monitor scale.')
        if transform % 2:
            width, height = height, width
        if mode == 1:
            width, height = round(width / scale), round(height / scale)
        monitors.append(Monitor(name, Rect(x, y, width, height), scale, primary))
    if not monitors:
        raise DisplayMappingError('No active GNOME monitors.')
    for index, monitor in enumerate(monitors):
        for other in monitors[index + 1:]:
            overlap = monitor.logical.intersect(other.logical)
            if overlap.width > 0 and overlap.height > 0:
                raise DisplayMappingError('Overlapping monitor geometry is ambiguous. Use Window or Full Screen.')
    return Layout(serial, tuple(monitors), mode)


async def read_gnome_layout():
    """Read-only, bounded D-Bus request; never block the Qt GUI thread."""
    bus = None
    try:
        bus = MessageBus()
        await asyncio.wait_for(bus.connect(), 3)
        version = await asyncio.wait_for(bus.call(Message(
            destination='org.gnome.Shell', path='/org/gnome/Shell',
            interface='org.freedesktop.DBus.Properties', member='Get', signature='ss',
            body=['org.gnome.Shell', 'ShellVersion'])), 3)
        if (version.message_type == MessageType.ERROR or not version.body
                or str(value(version.body[0])).split('.')[0] != '50'):
            raise DisplayMappingError('This GNOME screenshot backend version is not verified. Use Window or Full Screen.')
        reply = await asyncio.wait_for(bus.call(Message(
            destination='org.gnome.Mutter.DisplayConfig', path='/org/gnome/Mutter/DisplayConfig',
            interface='org.gnome.Mutter.DisplayConfig', member='GetCurrentState')), 3)
        if reply.message_type == MessageType.ERROR:
            raise DisplayMappingError('GNOME display geometry is unavailable. Use Window or Full Screen.')
        layout = parse_layout(reply.body)
        # Shell's whole-stage Screenshot starts at (0,0). Negative Qt origins
        # are fine, but do not infer an undocumented negative GNOME PNG origin.
        if layout.desktop.x != 0 or layout.desktop.y != 0:
            raise DisplayMappingError('The GNOME portal image origin cannot be verified. Use Window or Full Screen.')
        return layout
    except asyncio.CancelledError:
        raise
    except DisplayMappingError:
        raise
    except Exception as error:
        raise DisplayMappingError('Cannot establish the GNOME display mapping. Use Window or Full Screen.') from error
    finally:
        if bus is not None:
            bus.disconnect()


def compatibility_mapping(canvas_size, image_size):
    """Explicit single-canvas fallback for old/offscreen callers, not Wayland discovery."""
    w, h = canvas_size
    if w <= 0 or h <= 0 or image_size[0] <= 0 or image_size[1] <= 0:
        raise DisplayMappingError('Invalid screenshot or canvas size.')
    scale = image_size[0] / w
    if not math.isclose(scale, image_size[1] / h, abs_tol=1e-6):
        raise DisplayMappingError('Screenshot aspect ratio does not match the selection canvas.')
    return CaptureMapping(Layout(0, (Monitor('canvas', Rect(0, 0, w, h), scale, True),)), tuple(image_size), scale)
