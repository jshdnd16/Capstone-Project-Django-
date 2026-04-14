# materials/management/commands/seed_materials.py
# Run with: python manage.py seed_materials
#
# Creates sample categories, suppliers, and materials so you can
# immediately test the Phase 2 UI without entering data manually.

from django.core.management.base import BaseCommand
from materials.models import Category, Supplier, Material


class Command(BaseCommand):
    help = 'Seeds sample categories, suppliers, and materials'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding Materials data...")
        self.stdout.write("═" * 50)

        # ── Step 1: Create Categories ──────────────────
        categories_data = [
            {
                'category_name': 'Construction Chemicals',
                'description': 'Buildrite waterproofing, adhesives, grouts, and sealants'
            },
            {
                'category_name': 'Paints & Coatings',
                'description': 'Sinclair interior and exterior paints, primers, and varnishes'
            },
            {
                'category_name': 'Cement & Concrete',
                'description': 'Portland cement, concrete mix, and additives'
            },
            {
                'category_name': 'Steel & Metal',
                'description': 'Rebars, angle bars, G.I. sheets, and structural steel'
            },
            {
                'category_name': 'Lumber & Wood',
                'description': 'Lumber, plywood, marine boards, and engineered wood'
            },
            {
                'category_name': 'Electrical',
                'description': 'Wires, outlets, conduit pipes, and circuit breakers'
            },
            {
                'category_name': 'Plumbing',
                'description': 'PVC pipes, fittings, ball valves, and water tanks'
            },
        ]

        created_cats = {}
        self.stdout.write("\n  📂 Categories:")
        for data in categories_data:
            cat, created = Category.objects.get_or_create(
                category_name=data['category_name'],
                defaults={'description': data['description']}
            )
            created_cats[data['category_name']] = cat
            status = "✓ Created" if created else "• Exists "
            self.stdout.write(f"    {status}: {cat.category_name}")

        # ── Step 2: Create Suppliers ───────────────────
        suppliers_data = [
            {
                'company_name': 'Magna Prime Corporation',
                'contact_person': 'Rico Santos',
                'phone': '0917-111-2222',
                'email': 'orders@magnaprime.com',
                'address': 'Meycauayan, Bulacan',
                'supplier_type': 'Manufacturer',
                'is_primary': True,
                'status': 'Active',
            },
            {
                'company_name': 'Quezon Hardware Supply Co.',
                'contact_person': 'Maria Cruz',
                'phone': '0918-333-4444',
                'email': 'info@quezonhardware.com',
                'address': 'Lucena City, Quezon Province',
                'supplier_type': 'External',
                'is_primary': False,
                'status': 'Active',
            },
            {
                'company_name': 'Pacific Steel Trading',
                'contact_person': 'Jun Dela Cruz',
                'phone': '0920-555-6666',
                'email': 'pacific@steel.ph',
                'address': 'Calamba, Laguna',
                'supplier_type': 'External',
                'is_primary': False,
                'status': 'Active',
            },
            {
                'company_name': 'Batangas Lumber & Wood',
                'contact_person': 'Ana Ramos',
                'phone': '0921-777-8888',
                'email': 'batangaslumber@email.com',
                'address': 'Batangas City, Batangas',
                'supplier_type': 'External',
                'is_primary': False,
                'status': 'Active',
            },
        ]

        created_suppliers = {}
        self.stdout.write("\n  🏢 Suppliers:")
        for data in suppliers_data:
            sup, created = Supplier.objects.get_or_create(
                company_name=data['company_name'],
                defaults={k: v for k, v in data.items() if k != 'company_name'}
            )
            created_suppliers[data['company_name']] = sup
            status = "✓ Created" if created else "• Exists "
            self.stdout.write(f"    {status}: {sup.company_name}")

        magna = created_suppliers['Magna Prime Corporation']

        # ── Step 3: Create Materials ───────────────────
        materials_data = [
            # Buildrite Construction Chemicals (from Magna Prime)
            {
                'sku': 'BW-001',
                'name': 'Buildrite Waterproofing 20kg',
                'category': created_cats['Construction Chemicals'],
                'supplier': magna,
                'unit': 'bag',
                'current_cost': 850.00,
                'selling_price': 1100.00,
                'is_sales_inventory': True,
                'reorder_level': 20,
            },
            {
                'sku': 'BTA-001',
                'name': 'Buildrite Tile Adhesive 25kg',
                'category': created_cats['Construction Chemicals'],
                'supplier': magna,
                'unit': 'bag',
                'current_cost': 420.00,
                'selling_price': 560.00,
                'is_sales_inventory': True,
                'reorder_level': 30,
            },
            {
                'sku': 'BG-001',
                'name': 'Buildrite Tile Grout White 5kg',
                'category': created_cats['Construction Chemicals'],
                'supplier': magna,
                'unit': 'bag',
                'current_cost': 185.00,
                'selling_price': 250.00,
                'is_sales_inventory': True,
                'reorder_level': 50,
            },
            {
                'sku': 'BG-002',
                'name': 'Buildrite Tile Grout Gray 5kg',
                'category': created_cats['Construction Chemicals'],
                'supplier': magna,
                'unit': 'bag',
                'current_cost': 185.00,
                'selling_price': 250.00,
                'is_sales_inventory': True,
                'reorder_level': 50,
            },
            # Sinclair Paints (from Magna Prime)
            {
                'sku': 'SP-001',
                'name': 'Sinclair Permacoat Latex 4L White',
                'category': created_cats['Paints & Coatings'],
                'supplier': magna,
                'unit': 'gallons',
                'current_cost': 580.00,
                'selling_price': 750.00,
                'is_sales_inventory': True,
                'reorder_level': 25,
            },
            {
                'sku': 'SP-002',
                'name': 'Sinclair Permacoat Latex 4L Beige',
                'category': created_cats['Paints & Coatings'],
                'supplier': magna,
                'unit': 'gallons',
                'current_cost': 580.00,
                'selling_price': 750.00,
                'is_sales_inventory': True,
                'reorder_level': 20,
            },
            {
                'sku': 'SE-001',
                'name': 'Sinclair Gloss Enamel 4L White',
                'category': created_cats['Paints & Coatings'],
                'supplier': magna,
                'unit': 'gallons',
                'current_cost': 620.00,
                'selling_price': 820.00,
                'is_sales_inventory': True,
                'reorder_level': 20,
            },
            {
                'sku': 'SP-PRIMER-001',
                'name': 'Sinclair Primer Coat 4L',
                'category': created_cats['Paints & Coatings'],
                'supplier': magna,
                'unit': 'gallons',
                'current_cost': 480.00,
                'selling_price': 640.00,
                'is_sales_inventory': True,
                'reorder_level': 15,
            },
        ]

        self.stdout.write("\n  📦 Materials:")
        for data in materials_data:
            mat, created = Material.objects.get_or_create(
                sku=data['sku'],
                defaults={k: v for k, v in data.items() if k != 'sku'}
            )
            status = "✓ Created" if created else "• Exists "
            self.stdout.write(f"    {status}: {mat.name}")

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Materials seeding complete!")
        self.stdout.write(f"   Categories: {Category.objects.count()}")
        self.stdout.write(f"   Suppliers:  {Supplier.objects.count()}")
        self.stdout.write(f"   Materials:  {Material.objects.count()}")
        self.stdout.write("═" * 50)