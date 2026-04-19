# procurement/management/commands/seed_procurement.py
# Run with: python manage.py seed_procurement

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from materials.models import Supplier, Material
from procurement.models import ProcurementOrder, ProcurementItem
from inventory.utils import apply_stock_in

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds sample procurement orders including one received PO'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding Procurement data...")
        self.stdout.write("═" * 50)

        if ProcurementOrder.objects.exists():
            self.stdout.write("• Procurement orders already exist. Skipping.")
            return

        try:
            admin = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write("⚠️  Admin user not found.")
            return

        try:
            magna = Supplier.objects.get(is_primary=True)
        except Supplier.DoesNotExist:
            self.stdout.write("⚠️  Magna Prime not found. Run seed_materials first.")
            return

        today      = timezone.localdate()
        mats       = {
            m.sku: m for m in Material.objects.filter(
                sku__in=['BW-001', 'BTA-001', 'BG-001',
                         'BG-002', 'SP-001', 'SP-002',
                         'SE-001', 'SP-PRIMER-001']
            )
        }

        # ── PO 1: A received PO (represents last month's restocking) ──
        po1 = ProcurementOrder.objects.create(
            supplier               = magna,
            ordered_by             = admin,
            status                 = 'Received',
            order_method           = 'Email',
            expected_delivery_date = today,
            actual_delivery_date   = today,
            dr_number              = 'MAGNA-DR-2024-0498',
            stock_received         = True,
            approved_by            = admin,
            notes                  = 'Monthly restocking — seeded data',
        )

        po1_items = [
            ('BW-001',        100, None),
            ('BTA-001',       150, None),
            ('SP-001',         80, None),
            ('SP-PRIMER-001',  50, None),
        ]

        for sku, qty, cost in po1_items:
            mat = mats.get(sku)
            if mat:
                ProcurementItem.objects.create(
                    order        = po1,
                    material     = mat,
                    ordered_qty  = qty,
                    received_qty = qty,
                    unit_cost    = cost or mat.current_cost,
                )

        po1.recalculate_total()
        self.stdout.write(f"  ✓ PO#{po1.pk} [Received] — ₱{po1.total_amount:,.2f}")

        # ── PO 2: An active PO in Submitted status ──
        po2 = ProcurementOrder.objects.create(
            supplier               = magna,
            ordered_by             = admin,
            status                 = 'Submitted',
            order_method           = 'Email',
            expected_delivery_date = today + timezone.timedelta(days=7),
            stock_received         = False,
            notes                  = 'Mid-month restocking — seeded data',
        )

        po2_items = [
            ('BW-001',  50, None),
            ('BG-001',  80, None),
            ('BG-002',  60, None),
            ('SE-001',  40, None),
            ('SP-002',  30, None),
        ]

        for sku, qty, cost in po2_items:
            mat = mats.get(sku)
            if mat:
                ProcurementItem.objects.create(
                    order        = po2,
                    material     = mat,
                    ordered_qty  = qty,
                    received_qty = 0,
                    unit_cost    = cost or mat.current_cost,
                )

        po2.recalculate_total()
        self.stdout.write(f"  ✓ PO#{po2.pk} [Submitted] — ₱{po2.total_amount:,.2f}")

        # ── PO 3: A Draft PO ready for review ──
        po3 = ProcurementOrder.objects.create(
            supplier               = magna,
            ordered_by             = admin,
            status                 = 'Draft',
            order_method           = 'Email',
            expected_delivery_date = None,
            stock_received         = False,
            notes                  = 'Draft — awaiting review before sending to Magna Prime',
        )

        po3_items = [
            ('SP-001', 60, None),
            ('SP-PRIMER-001', 30, None),
        ]

        for sku, qty, cost in po3_items:
            mat = mats.get(sku)
            if mat:
                ProcurementItem.objects.create(
                    order        = po3,
                    material     = mat,
                    ordered_qty  = qty,
                    received_qty = 0,
                    unit_cost    = cost or mat.current_cost,
                )

        po3.recalculate_total()
        self.stdout.write(f"  ✓ PO#{po3.pk} [Draft] — ₱{po3.total_amount:,.2f}")

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Procurement seeding complete!")
        self.stdout.write(f"   Procurement Orders: {ProcurementOrder.objects.count()}")
        self.stdout.write("═" * 50)