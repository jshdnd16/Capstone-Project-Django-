# inventory/forms.py
# Three focused forms — one for each type of stock movement.
# Keeping them separate makes validation cleaner and the UI clearer.

from django import forms
from materials.models import Material
from .models import InventoryTransaction


# ─────────────────────────────────────────────────────────────
# SHARED WIDGET HELPER
# ─────────────────────────────────────────────────────────────
# Reusable attrs dict so every field gets consistent styling
_input_cls  = {'class': 'form-input'}
_select_cls = {'class': 'form-input'}


class StockInForm(forms.Form):
    """
    Form for recording incoming stock (deliveries from Magna Prime,
    returns from clients, or initial stock entry).
    
    We use a plain Form (not ModelForm) because we perform custom
    logic — updating Inventory.quantity AND creating a Transaction.
    """

    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs=_select_cls),
        help_text="Select the material that was received"
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={**_input_cls, 'placeholder': 'e.g., 50', 'min': '1'}),
        help_text="Number of units received"
    )
    reference_type = forms.ChoiceField(
        choices=[
            ('PROCUREMENT', 'Procurement / Delivery from Supplier'),
            ('RETURN',      'Return / Reversal'),
            ('INITIAL',     'Initial Stock Entry'),
            ('MANUAL',      'Other / Manual Entry'),
        ],
        widget=forms.Select(attrs=_select_cls)
    )
    reference_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={**_input_cls, 'placeholder': 'Optional: e.g., Procurement #12'}),
        help_text="Optional: the ID of the related procurement or document"
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            **_input_cls,
            'rows': 3,
            'placeholder': 'e.g., Received from Magna Prime DR#2024-001, 50 bags Buildrite Waterproofing'
        }),
        help_text="Optional notes about this delivery"
    )


class StockOutForm(forms.Form):
    """
    Form for recording outgoing stock (issued for a sales order,
    released to an architecture project, or other consumption).
    
    Validation ensures you cannot issue more stock than is available.
    """

    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs=_select_cls),
        help_text="Select the material being issued"
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={**_input_cls, 'placeholder': 'e.g., 10', 'min': '1'})
    )
    reference_type = forms.ChoiceField(
        choices=[
            ('SALES_ORDER',   'Sales Order'),
            ('ARCH_REQUEST',  'Architecture / Project Request'),
            ('MANUAL',        'Other / Manual Issue'),
        ],
        widget=forms.Select(attrs=_select_cls)
    )
    reference_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={**_input_cls, 'placeholder': 'Optional: e.g., Order #45'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            **_input_cls,
            'rows': 3,
            'placeholder': 'e.g., Issued for Sales Order #45 — Buildrite Hardware Tiaong'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show materials that actually have stock > 0
        # This prevents issuing stock for out-of-stock items right in the form
        from .models import Inventory
        in_stock_ids = Inventory.objects.filter(
            quantity__gt=0
        ).values_list('material_id', flat=True)
        self.fields['material'].queryset = Material.objects.filter(
            is_active=True,
            id__in=in_stock_ids
        ).order_by('name')

    def clean(self):
        """
        Cross-field validation: check that we have enough stock
        before allowing the transaction to be submitted.
        """
        cleaned_data = super().clean()
        material = cleaned_data.get('material')
        qty      = cleaned_data.get('quantity')

        if material and qty:
            try:
                from .models import Inventory
                inv = Inventory.objects.get(material=material)
                if qty > inv.quantity:
                    raise forms.ValidationError(
                        f"Insufficient stock. Current stock: {inv.quantity} {material.unit}. "
                        f"You requested: {qty} {material.unit}."
                    )
            except Inventory.DoesNotExist:
                raise forms.ValidationError(
                    "No inventory record found for this material. "
                    "Please add initial stock first using Stock In."
                )

        return cleaned_data


class StockAdjustmentForm(forms.Form):
    """
    Form for correcting stock levels due to physical recounts,
    spoilage, theft, or data entry errors.
    
    The key difference from IN/OUT: the admin enters the NEW correct quantity
    directly, and the system calculates the adjustment automatically.
    This mirrors how a physical stock-take works in a warehouse.
    """

    REASON_CHOICES = [
        ('Physical recount',     'Physical Recount / Stocktake'),
        ('Spoilage / Damage',    'Spoilage or Damaged Goods'),
        ('Data entry correction','Data Entry Correction'),
        ('Theft / Loss',         'Theft or Loss'),
        ('Other',                'Other'),
    ]

    material = forms.ModelChoiceField(
        queryset=Material.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs=_select_cls)
    )
    # The correct quantity after physical count — not a delta
    new_quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={
            **_input_cls,
            'placeholder': 'Enter the correct stock count',
            'min': '0'
        }),
        help_text="Enter the ACTUAL quantity after physical count. The system will calculate the difference."
    )
    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        widget=forms.Select(attrs=_select_cls)
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            **_input_cls,
            'rows': 3,
            'placeholder': 'Describe why the adjustment is needed...'
        })
    )
