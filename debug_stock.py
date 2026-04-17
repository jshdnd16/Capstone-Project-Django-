# import os, django
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mitra_project.settings')
# django.setup()

# from inventory.models import Inventory
# from materials.models import Material
# from django.db.models import F

# print("=== All Inventory rows ===")
# for i in Inventory.objects.select_related('material').all():
#     print(f"  {i.material.name}: qty={i.quantity}, reorder={i.material.reorder_level}, low={i.is_low_stock}")

# print()
# total_active = Material.objects.filter(is_active=True).count()
# total_inv = Inventory.objects.count()
# print(f"Total active materials: {total_active}")
# print(f"Total inventory rows: {total_inv}")

# inv_ids = set(Inventory.objects.values_list('material_id', flat=True))
# no_inv = Material.objects.filter(is_active=True).exclude(id__in=inv_ids).count()
# print(f"Materials with NO inventory row: {no_inv}")

# low_with_inv = Inventory.objects.filter(
#     quantity__lte=F('material__reorder_level'),
#     material__is_active=True
# ).count()
# print(f"Low stock (with inv row): {low_with_inv}")
# print(f"Low stock total: {low_with_inv + no_inv}")

# out_with_inv = Inventory.objects.filter(quantity__lte=0, material__is_active=True).count()
# print(f"Out of stock (with inv): {out_with_inv}")
# print(f"Out of stock total: {out_with_inv + no_inv}")

# # Check if exception is being swallowed
# print("\n=== Testing dashboard query ===")
# try:
#     materials_with_inv = set(Inventory.objects.values_list('material_id', flat=True))
#     low_stock_with_inv = Inventory.objects.filter(
#         quantity__lte=F('material__reorder_level'),
#         material__is_active=True
#     ).count()
#     low_stock_no_inv = Material.objects.filter(
#         is_active=True
#     ).exclude(id__in=materials_with_inv).count()
#     low_stock_items = low_stock_with_inv + low_stock_no_inv
#     print(f"Dashboard low_stock_items would be: {low_stock_items}")
# except Exception as e:
#     print(f"EXCEPTION: {e}")
