"""Batch cameo decoding on the launcher's worker and cache missing assets."""

from functools import wraps
import threading


_preview_loader = None


def deferred_preview(loader):
    """Share the cameo worker with custom sidebar PNG conversion."""
    @wraps(loader)
    def preview(value):
        if _preview_loader is not None and threading.current_thread() is threading.main_thread():
            return _preview_loader.request_preview(loader, value)
        return loader(value)
    return preview


def deferred_cameos(unit_loader, power_loader, *, synchronous=False):
    """Keep public loaders usable by workers and defer only Tk requests."""
    bound = None

    class Loader:
        def __init__(self, app):
            self.app = app
            self.units = {}
            self.powers = {}
            self.previews = {}
            self.pending_previews = set()
            self.pending_units = set()
            self.pending_powers = set()
            self.scheduled = None
            self.running = False
            self.revision = 0

        def has_pending(self):
            return bool(self.pending_units or self.pending_powers or self.pending_previews)

        def request_preview(self, loader, value):
            key = loader, str(value)
            if key not in self.previews:
                self.pending_previews.add(key)
                if not self.running and self.scheduled is None:
                    self.scheduled = self.app.after(1, self.start)
            return self.previews.get(key)

        def request(self, ids, overrides=None, *, powers=False):
            ids = tuple(dict.fromkeys(str(value).upper() for value in ids))
            overrides = {str(key).upper(): str(value) for key, value in (overrides or {}).items() if value}
            cache = self.powers if powers else self.units
            pending = self.pending_powers if powers else self.pending_units
            result = {}
            for identity in ids:
                key = (identity, overrides.get(identity, '')) if powers else identity
                if key not in cache:
                    pending.add(key)
                elif cache[key] is not None:
                    result[identity] = cache[key]
            if self.has_pending() and not self.running and self.scheduled is None:
                self.scheduled = self.app.after(1, self.start)
            return result

        def start(self):
            self.scheduled = None
            if self.running or not self.has_pending():
                return
            # Let the current foreground job finish before changing its modal.
            if self.app.busy_depth:
                self.scheduled = self.app.after(50, self.start)
                return
            units, powers, previews = self.pending_units, self.pending_powers, self.pending_previews
            self.pending_previews = set()
            self.pending_units, self.pending_powers = set(), set()
            self.running = True

            def work():
                options = {'synchronous': True} if synchronous else {}
                unit_paths = unit_loader(sorted(units), **options) if units else {}
                power_paths = {}
                # One icon may have different sidebar overrides in different
                # views. Batch by override while retaining every cache key.
                groups = {}
                for identity, override in powers:
                    groups.setdefault(override, []).append(identity)
                for override, identities in groups.items():
                    paths = power_loader(identities, {identity: override for identity in identities} if override else None, **options)
                    power_paths.update({(identity, override): paths.get(identity) for identity in identities})
                preview_paths = {}
                for loader, value in previews:
                    try:
                        preview_paths[loader, value] = loader(value)
                    except (OSError, ValueError):
                        preview_paths[loader, value] = None
                return unit_paths, power_paths, preview_paths

            def finish(result):
                unit_paths, power_paths, preview_paths = result
                self.previews.update(preview_paths)
                self.pending_units.difference_update(units)
                self.pending_powers.difference_update(powers)
                self.pending_previews.difference_update(previews)
                self.units.update({identity: unit_paths.get(identity) for identity in units})
                self.powers.update(power_paths)
                self.running = False
                self.refresh()
                if self.has_pending() and self.scheduled is None:
                    self.scheduled = self.app.after(1, self.start)

            def failed(exc, detail):
                # Remember unavailable artwork for this session. Retrying a
                # missing icon on every tab switch is expensive on slow disks.
                self.previews.update({key: None for key in previews})
                self.units.update({identity: None for identity in units})
                self.powers.update({key: None for key in powers})
                self.running = False
                self.app.append_log(f'Cameo loading failed: {exc}', error=True)
                self.refresh()
                if self.has_pending() and self.scheduled is None:
                    self.scheduled = self.app.after(1, self.start)

            self.app.run_in_background('Loading cameos…', 'Reading artwork for this page. Please wait.', work, finish, failed)

        def refresh(self):
            app = self.app
            self.revision += 1
            app.advanced_unit_cameo_paths = None
            app.unlock_dashboard_signature = None
            app.unlock_dashboard_structure_signatures = {}
            app._unlocks_view_dirty = True
            # Refresh consumers only while visible. Hidden pages pick up the
            # shared cache when opened, without rebuilding their widgets now.
            app.refresh_active_advanced_view()
            if app.unlock_summary_visible():
                app.refresh_unlocks_view()
            elif app.unlock_dashboard_visible():
                app.refresh_unlock_dashboard()
            if hasattr(app, 'refresh_visible_shop_panel') and app.shop_mode_selected():
                app.refresh_visible_shop_panel()

    @wraps(unit_loader)
    def units(ids, **options):
        if bound is not None and threading.current_thread() is threading.main_thread():
            return bound.request(ids)
        return unit_loader(ids, **options)

    @wraps(power_loader)
    def powers(ids, sidebar_overrides=None, **options):
        if bound is not None and threading.current_thread() is threading.main_thread():
            return bound.request(ids, sidebar_overrides, powers=True)
        return power_loader(ids, sidebar_overrides, **options)

    def bind(app):
        nonlocal bound
        global _preview_loader
        bound = Loader(app)
        app._cameo_loader = bound
        _preview_loader = bound

    return units, powers, bind
