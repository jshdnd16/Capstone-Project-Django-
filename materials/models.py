# materials/models.py
# Three models that form the foundation of the product catalog.
#
# Category  → groups materials (e.g., Construction Chemicals, Paints)
# Supplier  → companies that provide materials (Magna Prime, external vendors)
# Material  → individual products (Buildrite Waterproofing, Sinclair Paint)

from django.db import models


class Category(models.Model):
    """
    Groups materials into logical buckets.
    
    Examples:
    - Construction Chemicals  (Buildrite products)
    - Paints & Coatings       (Sinclair products)
    - Cement & Concrete
    - Steel & Metal
    """

    category_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="e.g., Construction Chemicals, Paints & Coatings"
    )
    description = models.TextField(
        blank=True,
        help_text="Brief description of what belongs in this category"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.category_name

    def material_count(self):
        """
        Returns how many active materials are in this category.
        Used to show the count on the category list page.
        """
        return self.materials.filter(is_active=True).count()

    class Meta:
        ordering = ['category_name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'


class Supplier(models.Model):
    """
    Companies that supply materials to Mitra.
    
    Two types:
    - Manufacturer: Magna Prime (makes Buildrite & Sinclair products)
    - External: Other suppliers used by the Architecture department
    """

    SUPPLIER_TYPE_CHOICES = [
        ('Manufacturer', 'Manufacturer'),
        ('External', 'External'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]

    company_name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    supplier_type = models.CharField(
        max_length=20,
        choices=SUPPLIER_TYPE_CHOICES,
        default='External',
        help_text="Manufacturer = Magna Prime; External = Architecture suppliers"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='Active'
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Mark as True for Magna Prime — the main manufacturer"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name

    class Meta:
        ordering = ['company_name']
        verbose_name = 'Supplier'
        verbose_name_plural = 'Suppliers'


class Material(models.Model):
    """
    Individual products in the Mitra catalog.
    
    Two types controlled by is_sales_inventory:
    - Sales Inventory (True):  Buildrite/Sinclair products stocked in the warehouse
    - External (False):        Materials sourced externally for Architecture projects
    
    We use a soft-delete pattern (is_active) instead of hard-deleting,
    because materials will be referenced by future orders and inventory records.
    """

    UNIT_CHOICES = [
        ('bag', 'Bag'),
        ('pcs', 'Pieces'),
        ('liters', 'Liters'),
        ('kg', 'Kilograms'),
        ('gallons', 'Gallons'),
        ('rolls', 'Rolls'),
        ('boxes', 'Boxes'),
        ('sets', 'Sets'),
        ('drums', 'Drums'),
        ('tubes', 'Tubes'),
        ('sheets', 'Sheets'),
        ('lengths', 'Lengths'),
    ]

    sku = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Optional: product code or barcode for quick lookup"
    )
    name = models.CharField(
        max_length=200,
        help_text="e.g., Buildrite Waterproofing 20kg, Sinclair Permacoat 4L White"
    )
    description = models.TextField(
        blank=True,
        help_text="Short product description, highlights, or usage notes"
    )
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        help_text="Optional product photo to show in the catalog"
    )

    # ForeignKeys use PROTECT so we can't accidentally delete a Category or
    # Supplier that still has materials attached to it.
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='materials'
    )
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='materials'
    )

    unit = models.CharField(max_length=20, choices=UNIT_CHOICES)

    # Pricing
    current_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Buying price from Magna Prime or supplier"
    )
    selling_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price charged to hardware stores or clients"
    )

    is_sales_inventory = models.BooleanField(
        default=True,
        help_text="Check if this product is stocked in the Sales warehouse"
    )
    reorder_level = models.IntegerField(
        default=10,
        help_text="Show low-stock alert when stock falls below this number"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide material without deleting historical records"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)   # Auto-updates on every save

    def __str__(self):
        return self.name

    @property
    def margin_percentage(self):
        """
        Calculates the profit margin as a percentage.
        Formula: ((selling_price - cost) / cost) * 100
        
        Example: cost=850, price=1100 → margin = 29.4%
        """
        if self.current_cost and self.current_cost > 0:
            margin = ((self.selling_price - self.current_cost) / self.current_cost) * 100
            return round(float(margin), 1)
        return 0

    @property
    def profit_per_unit(self):
        """How much gross profit is made per unit sold."""
        return self.selling_price - self.current_cost

    class Meta:
        ordering = ['name']
        verbose_name = 'Material'
        verbose_name_plural = 'Materials'