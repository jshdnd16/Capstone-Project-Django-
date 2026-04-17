# sales/management/commands/seed_sales.py
# Run with: python manage.py seed_sales
#
# Creates sample clients and a few orders so the sales pages
# aren't empty on first load.

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from sales.models import Client, Order, OrderItem
from materials.models import Material

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds sample clients and demo orders'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding Sales data...")
        self.stdout.write("═" * 50)

        # ── Clients ─────────────────────────────────────────────
        clients_data = [
            {
                'client_name':    'Buildrite Hardware Tiaong',
                'contact_person': 'Ramon Villanueva',
                'phone':          '0917-234-5678',
                'address':        'National Highway, Tiaong, Quezon',
                'client_type':    'Hardware Store',
                'delivery_zone':  'Central Quezon',
            },
            {
                'client_name':    'Sariaya General Hardware',
                'contact_person': 'Ligaya Santos',
                'phone':          '0918-345-6789',
                'address':        'Maharlika Highway, Sariaya, Quezon',
                'client_type':    'Hardware Store',
                'delivery_zone':  'Central Quezon',
            },
            {
                'client_name':    'Lucky Builders Supply Lucena',
                'contact_person': 'Edgar Reyes',
                'phone':          '0919-456-7890',
                'address':        'Quezon Ave., Lucena City',
                'client_type':    'Hardware Store',
                'delivery_zone':  'Lucena City',
            },
            {
                'client_name':    'NB Construction',
                'contact_person': 'Noel Bautista',
                'phone':          '0920-567-8901',
                'address':        'Candelaria, Quezon',
                'client_type':    'Contractor',
                'delivery_zone':  'North Quezon',
            },
            {
                'client_name':    'Walk-in Customer',
                'contact_person': '',
                'phone':          'N/A',
                'address':        'Mitra Planners Office',
                'client_type':    'Walk-in',
                'delivery_zone':  'Pick-up',
            },
        ]

        created_clients = {}
        self.stdout.write("\n  👥 Clients:")
        for data in clients_data:
            client, created = Client.objects.get_or_create(
                client_name=data['client_name'],
                defaults={k: v for k, v in data.items() if k != 'client_name'}
            )
            created_clients[data['client_name']] = client
            status = "✓ Created" if created else "• Exists "
            self.stdout.write(f"    {status}: {client.client_name}")

        # ── Sample Orders ─────────────────────────────────────
        try:
            admin_user = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write("\n  ⚠️  Admin user not found. Skipping orders.")
            return

        # Only create orders if none exist
        if Order.objects.exists():
            self.stdout.write("\n  • Orders already exist, skipping order seed.")
        else:
            # Get materials for order items
            mats = {m.sku: m for m in Material.objects.filter(
                sku__in=['BW-001', 'BTA-001', 'SP-001', 'BG-001']
            )}

            orders_data = [
                {
                    'client':       'Buildrite Hardware Tiaong',
                    'order_type':   'Regular',
                    'status':       'Pending',
                    'payment_status': 'Unpaid',
                    'notes':        'Deliver before Friday.',
                    'items': [
                        ('BW-001', 10, None),   # (sku, qty, price override)
                        ('BTA-001', 20, None),
                    ],
                },
                {
                    'client':       'Sariaya General Hardware',
                    'order_type':   'Regular',
                    'status':       'Confirmed',
                    'payment_status': 'Partial',
                    'notes':        '',
                    'items': [
                        ('SP-001', 15, None),
                        ('BG-001', 30, None),
                    ],
                },
                {
                    'client':       'NB Construction',
                    'order_type':   'Bulk',
                    'status':       'Completed',
                    'payment_status': 'Paid',
                    'notes':        'Bulk order for Candelaria project.',
                    'items': [
                        ('BW-001', 5, None),
                    ],
                },
            ]

            self.stdout.write("\n  📋 Orders:")
            for data in orders_data:
                client = created_clients.get(data['client'])
                if not client:
                    continue

                order = Order.objects.create(
                    client=client,
                    created_by=admin_user,
                    order_type=data['order_type'],
                    status=data['status'],
                    payment_status=data['payment_status'],
                    notes=data['notes'],
                    stock_deducted=(data['status'] in ('Preparing', 'Out for Delivery', 'Completed')),
                )

                for sku, qty, price in data['items']:
                    mat = mats.get(sku)
                    if mat:
                        OrderItem.objects.create(
                            order=order,
                            material=mat,
                            quantity=qty,
                            price_at_sale=price or mat.selling_price,
                        )

                order.recalculate_total()
                self.stdout.write(f"    ✓ Order #{order.pk} — {client.client_name} ({order.status}) ₱{order.total_amount}")

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Sales seeding complete!")
        self.stdout.write(f"   Clients: {Client.objects.count()}")
        self.stdout.write(f"   Orders:  {Order.objects.count()}")
        self.stdout.write("═" * 50)