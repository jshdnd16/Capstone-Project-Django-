# delivery/management/commands/seed_deliveries.py
# Run with: python manage.py seed_deliveries

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from sales.models import Order
from delivery.models import Delivery, DeliveryStatusLog

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds sample delivery records'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding Delivery data...")
        self.stdout.write("═" * 50)

        if Delivery.objects.exists():
            self.stdout.write("• Deliveries already exist. Skipping.")
            return

        try:
            admin = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write("⚠️  Admin user not found.")
            return

        # Use a completed order for the demo delivery
        completed_order = Order.objects.filter(status='Completed').first()

        if not completed_order:
            self.stdout.write("⚠️  No completed orders found. Run seed_sales first.")
            return

        today = timezone.localdate()

        deliveries_data = [
            {
                'delivery_type': 'Sales Order',
                'order':         completed_order,
                'driver_name':   'Pedro Macaraeg',
                'delivery_team': 'Mitra',
                'vehicle_plate': 'QDZ 7821',
                'schedule_date': today,
                'start_location': 'Mitra Planners — Main Warehouse, Quezon Province',
                'end_location':   completed_order.client.address or 'Tiaong, Quezon',
                'status':         'Received',
                'dr_number':      'DR-2024-0042',
                'received_by':    'Ramon Villanueva',
                'notes':          'Delivered on time. No issues.',
            },
            {
                'delivery_type': 'Sales Order',
                'order':         None,
                'driver_name':   'Ernesto Labrador',
                'delivery_team': 'Mitra',
                'vehicle_plate': 'QDZ 3390',
                'schedule_date': today,
                'start_location': 'Mitra Planners — Main Warehouse, Quezon Province',
                'end_location':   'Sariaya General Hardware, Maharlika Highway',
                'status':         'Scheduled',
                'dr_number':      '',
                'received_by':    '',
                'notes':          'Call client 30 minutes before arrival.',
            },
        ]

        self.stdout.write("\n  🚚 Deliveries:")
        for data in deliveries_data:
            d = Delivery.objects.create(
                delivery_type = data['delivery_type'],
                order         = data.get('order'),
                driver_name   = data['driver_name'],
                delivery_team = data['delivery_team'],
                vehicle_plate = data['vehicle_plate'],
                schedule_date = data['schedule_date'],
                start_location = data['start_location'],
                end_location  = data['end_location'],
                status        = data['status'],
                dr_number     = data['dr_number'],
                received_by   = data['received_by'],
                notes         = data['notes'],
                created_by    = admin,
            )
            DeliveryStatusLog.objects.create(
                delivery=d, old_status='', new_status='Scheduled',
                changed_by=admin, notes='Seeded delivery.'
            )
            if d.status == 'Received':
                DeliveryStatusLog.objects.create(
                    delivery=d, old_status='Scheduled',
                    new_status='Received', changed_by=admin,
                    notes=f"DR#{d.dr_number}. Received by {d.received_by}."
                )
            self.stdout.write(f"  ✓ Delivery #{d.pk} — {d.driver_name} ({d.status})")

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Delivery seeding complete!")
        self.stdout.write(f"   Deliveries: {Delivery.objects.count()}")
        self.stdout.write("═" * 50)