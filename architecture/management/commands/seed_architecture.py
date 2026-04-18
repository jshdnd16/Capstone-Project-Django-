# architecture/management/commands/seed_architecture.py
# Run with: python manage.py seed_architecture

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from materials.models import Material
from architecture.models import Project, BOQHeader, BOQItem

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds sample architecture projects and BOQs'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding Architecture data...")
        self.stdout.write("═" * 50)

        # Use admin as the architect for demo data
        try:
            admin = User.objects.get(username='admin')
        except User.DoesNotExist:
            self.stdout.write("⚠️  Admin user not found. Run seed_roles first.")
            return

        if Project.objects.exists():
            self.stdout.write("• Projects already exist. Skipping.")
            return

        # Get some materials for BOQ items
        mats = {
            m.sku: m for m in Material.objects.filter(
                sku__in=['BW-001', 'BTA-001', 'BG-001', 'SP-001', 'SP-PRIMER-001']
            )
        }

        projects_data = [
            {
                'project_name': 'Lucena City Residential Renovation',
                'client_name':  'Spouses De Leon',
                'location':     'Brgy. Gulang-Gulang, Lucena City, Quezon',
                'status':       'Ongoing',
                'budget':       850000.00,
                'description':  'Full interior renovation including tile, waterproofing, and painting.',
                'boq_items': [
                    ('BW-001',       30,  None),
                    ('BTA-001',      60,  None),
                    ('BG-001',       80,  None),
                    ('SP-PRIMER-001', 20, None),
                    ('SP-001',       40,  None),
                ],
                'boq_final': True,
            },
            {
                'project_name': 'Tiaong Commercial Building — Phase 1',
                'client_name':  'Villanueva Properties Inc.',
                'location':     'National Highway, Tiaong, Quezon',
                'status':       'Planning',
                'budget':       2500000.00,
                'description':  'Three-storey commercial building. Phase 1: structural and waterproofing.',
                'boq_items': [
                    ('BW-001', 120, None),
                    ('BTA-001', 200, None),
                ],
                'boq_final': False,
            },
        ]

        self.stdout.write("\n  🏗️ Projects & BOQs:")
        for data in projects_data:
            project = Project.objects.create(
                project_name = data['project_name'],
                client_name  = data['client_name'],
                location     = data['location'],
                architect    = admin,
                status       = data['status'],
                budget       = data['budget'],
                description  = data['description'],
            )

            # Create a BOQ for each project
            boq = BOQHeader.objects.create(
                project    = project,
                version    = 1,
                created_by = admin,
                is_final   = data['boq_final'],
                notes      = 'Initial BOQ — system seed data',
            )

            for sku, qty, cost_override in data['boq_items']:
                mat = mats.get(sku)
                if mat:
                    BOQItem.objects.create(
                        boq          = boq,
                        material     = mat,
                        required_qty = qty,
                        unit_cost    = cost_override or mat.current_cost,
                        source_type  = 'Sales Inventory',
                    )

            boq.recalculate_total()
            status_tag = "[FINAL]" if boq.is_final else "[Draft]"
            self.stdout.write(
                f"  ✓ {project.project_name}\n"
                f"      BOQ v1 {status_tag} — ₱{boq.total_estimate:,.2f}"
            )

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Architecture seeding complete!")
        self.stdout.write(f"   Projects : {Project.objects.count()}")
        self.stdout.write(f"   BOQs     : {BOQHeader.objects.count()}")
        self.stdout.write("═" * 50)