# accounts/management/commands/seed_roles.py
#
# A Django management command — runs with:
#   python manage.py seed_roles
#
# This creates the 5 default roles and a superuser Admin account
# so you can immediately log in after setup.
#
# Management commands live in:
#   accounts/management/commands/seed_roles.py
# The folder structure is required by Django.

from django.core.management.base import BaseCommand
from accounts.models import Role, User


class Command(BaseCommand):
    """Seeds the database with default roles and an initial Admin account."""

    help = 'Creates default roles and initial Admin user account'

    def handle(self, *args, **options):
        self.stdout.write("═" * 50)
        self.stdout.write("🌱 Seeding Mitra PWA initial data...")
        self.stdout.write("═" * 50)

        # ── Create the 5 default roles ──
        roles_data = [
            {
                'role_name': 'Admin',
                'permissions': {
                    'can_create_users': True,
                    'can_view_all': True,
                    'can_approve_orders': True,
                    'can_manage_inventory': True,
                    'can_view_reports': True,
                    'can_delete_records': True,
                }
            },
            {
                'role_name': 'Sales',
                'permissions': {
                    'can_create_orders': True,
                    'can_view_orders': True,
                    'can_manage_clients': True,
                    'can_view_inventory': True,
                    'can_view_reports': False,
                }
            },
            {
                'role_name': 'Architect',
                'permissions': {
                    'can_create_projects': True,
                    'can_create_boq': True,
                    'can_request_materials': True,
                    'can_view_inventory': True,
                    'can_view_orders': False,
                }
            },
            {
                'role_name': 'Warehouse',
                'permissions': {
                    'can_manage_inventory': True,
                    'can_view_inventory': True,
                    'can_create_procurement': True,
                    'can_receive_materials': True,
                    'can_view_orders': True,
                }
            },
            {
                'role_name': 'Driver',
                'permissions': {
                    'can_view_deliveries': True,
                    'can_update_delivery_status': True,
                    'can_view_orders': False,
                    'can_view_inventory': False,
                }
            },
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                role_name=role_data['role_name'],
                defaults={'permissions': role_data['permissions']}
            )
            if created:
                self.stdout.write(f"  ✓ Created role: {role.role_name}")
            else:
                self.stdout.write(f"  • Role already exists: {role.role_name}")

        # ── Create initial Admin superuser ──
        if not User.objects.filter(username='admin').exists():
            admin_role = Role.objects.get(role_name='Admin')
            admin_user = User.objects.create_superuser(
                username='admin',
                password='Admin@Mitra2024',   # CHANGE THIS after first login!
                fullname='System Administrator',
                email='admin@mitraplanners.com',
                role=admin_role,
                department='Management',
            )
            self.stdout.write("")
            self.stdout.write("  ✓ Created Admin account:")
            self.stdout.write(f"    Username : admin")
            self.stdout.write(f"    Password : Admin@Mitra2024")
            self.stdout.write("    ⚠️  CHANGE THIS PASSWORD after first login!")
        else:
            self.stdout.write("  • Admin account already exists")

        self.stdout.write("")
        self.stdout.write("═" * 50)
        self.stdout.write("✅ Seeding complete! You can now run the server.")
        self.stdout.write("   Login at: http://localhost:8000/accounts/login/")
        self.stdout.write("═" * 50)