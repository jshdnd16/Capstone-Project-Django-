# inventory/management/commands/seed_inventory.py
# Run with: python manage.py seed_inventory
#
# Creates initial stock levels for all materials seeded in Phase 2.
# Each material gets a realistic starting quantity so the stock
# overview page isn't empty on first use.

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from materials.models import Material
from inventory.utils import apply_stock_in

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds initial inventory stock levels for all materials'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding initial inventory...")
        self.stdout.write("═" * 50)

        # Use the admin account to record these initial entries
        try:
            admin_user = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write("  ⚠️  Admin user not found. Run seed_roles first.")
            return

        # Initial stock levels: material SKU → starting quantity
        # These represent a realistic mid-month snapshot
        initial_stock = {
            'BW-001':       45,   # Buildrite Waterproofing 20kg
            'BTA-001':      80,   # Buildrite Tile Adhesive 25kg
            'BG-001':       120,  # Buildrite Tile Grout White
            'BG-002':       95,   # Buildrite Tile Grout Gray
            'SP-001':       60,   # Sinclair Permacoat White
            'SP-002':       35,   # Sinclair Permacoat Beige — intentionally low
            'SE-001':       28,   # Sinclair Gloss Enamel White — below reorder
            'SP-PRIMER-001': 8,   # Sinclair Primer — very low, triggers alert
        }

        self.stdout.write("\n  📦 Setting initial stock levels:")

        for sku, qty in initial_stock.items():
            try:
                material = Material.objects.get(sku=sku)

                # Check if stock already exists to avoid double-seeding
                from inventory.models import Inventory
                if Inventory.objects.filter(material=material, quantity__gt=0).exists():
                    self.stdout.write(f"  • Already has stock: {material.name}")
                    continue

                inv = apply_stock_in(
                    material       = material,
                    quantity       = qty,
                    user           = admin_user,
                    reference_type = 'INITIAL',
                    remarks        = 'Initial stock entry — system setup'
                )

                # Flag for low-stock items in the output
                alert = " ⚠️  LOW" if inv.is_low_stock else ""
                self.stdout.write(
                    f"  ✓ {material.name:<40} {qty:>4} {material.unit}{alert}"
                )

            except Material.DoesNotExist:
                self.stdout.write(f"  ⚠️  Material with SKU '{sku}' not found. Skipping.")

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Inventory seeding complete!")

        from inventory.models import Inventory
        from django.db.models import F
        total     = Inventory.objects.count()
        low_stock = Inventory.objects.filter(
            quantity__gt=0,
            quantity__lte=F('material__reorder_level')
        ).count()
        out_stock = Inventory.objects.filter(quantity__lte=0).count()

        self.stdout.write(f"   Total inventory records : {total}")
        self.stdout.write(f"   Low stock alerts        : {low_stock}")
        self.stdout.write(f"   Out of stock            : {out_stock}")
        self.stdout.write("═" * 50)