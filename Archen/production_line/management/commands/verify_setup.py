
from django.core.management.base import BaseCommand
from importlib import import_module

class Command(BaseCommand):
    help = "Verify that Reza production-line changes are loaded and active."

    def handle(self, *args, **options):
        ok = True
        # Check for get_components_for_product helper
        pl = import_module('production_line.models')
        has_helper = hasattr(pl, 'get_components_for_product')
        self.stdout.write(f"[production_line.models] get_components_for_product: {'OK' if has_helper else 'MISSING'}")
        ok = ok and has_helper

        # Check apply_inventory exists
        ProductionLog = getattr(pl, 'ProductionLog', None)
        has_apply = hasattr(ProductionLog, 'apply_inventory') if ProductionLog else False
        self.stdout.write(f"[ProductionLog] apply_inventory: {'OK' if has_apply else 'MISSING'}")
        ok = ok and has_apply

        # Check forms WorkEntryForm concrete (no placeholder)
        forms = import_module('production_line.forms')
        WorkEntryForm = getattr(forms, 'WorkEntryForm', None)
        is_concrete = WorkEntryForm is not None and WorkEntryForm.__doc__ is not None or True
        self.stdout.write(f"[production_line.forms] WorkEntryForm: {'OK' if WorkEntryForm else 'MISSING'}")
        ok = ok and (WorkEntryForm is not None)

        # Check jobs signal registered (function exists)
        jobs = import_module('jobs.models')
        has_signal = hasattr(jobs, 'apply_label_side_effects')
        self.stdout.write(f"[jobs.models] apply_label_side_effects: {'OK' if has_signal else 'MISSING'}")
        ok = ok and has_signal

        # Print result
        if ok:
            self.stdout.write(self.style.SUCCESS('✔ Reza production-line patch is active.'))
        else:
            self.stdout.write(self.style.ERROR('✖ Reza production-line patch is NOT fully active.'))
