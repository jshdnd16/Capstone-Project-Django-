# procurement/forms.py
# Forms for the Procurement module.
#
# ProcurementOrderForm  → Create the PO header
#                         (supplier, expected date, order method, notes)
#
# ProcurementItemForm   → One line item (material, qty, unit cost)
# ProcurementItemFormSet→ Inline formset for multiple items on one page
#
# ProcurementUpdateForm → Edit header fields while still in Draft
#
# ReceivingForm         → Filled when marking a PO as Received.
#                         Records received_qty per item (may differ
#                         from ordered_qty), DR number, and actual date.

from django import forms
from django.forms import inlineformset_factory

from .models import ProcurementOrder, ProcurementItem
from materials.models import Material, Supplier

# ── Shared CSS helpers ────────────────────────────────────────
_input  = {'class': 'form-input'}
_select = {'class': 'form-input'}
_area   = {'class': 'form-input', 'rows': 3}
_date   = {'class': 'form-input', 'type': 'date'}


class ProcurementOrderForm(forms.ModelForm):
    """
    Creates a new procurement order header.
    Items are added below via ProcurementItemFormSet.
    """

    class Meta:
        model  = ProcurementOrder
        fields = [
            'supplier', 'order_method',
            'expected_delivery_date', 'notes',
        ]
        widgets = {
            'supplier':              forms.Select(attrs=_select),
            'order_method':          forms.Select(attrs=_select),
            'expected_delivery_date': forms.DateInput(attrs=_date),
            'notes': forms.Textarea(attrs={
                **_area,
                'placeholder': 'Any special instructions for this order...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active suppliers
        self.fields['supplier'].queryset = Supplier.objects.filter(
            status='Active'
        ).order_by('-is_primary', 'company_name')
        self.fields['supplier'].empty_label        = '— Select supplier —'
        self.fields['expected_delivery_date'].required = False


class ProcurementItemForm(forms.ModelForm):
    """
    One material line inside a procurement order.
    unit_cost auto-fills from the material's current_cost via JavaScript.
    """

    class Meta:
        model  = ProcurementItem
        fields = ['material', 'ordered_qty', 'unit_cost']
        widgets = {
            'material':    forms.Select(attrs={
                **_select,
                'class': 'form-input po-material-select',
            }),
            'ordered_qty': forms.NumberInput(attrs={
                **_input,
                'placeholder': '0', 'min': '1',
                'class': 'form-input po-qty-input',
            }),
            'unit_cost':   forms.NumberInput(attrs={
                **_input,
                'placeholder': '0.00', 'step': '0.01', 'min': '0',
                'class': 'form-input po-cost-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.filter(
            is_active=True
        ).select_related('category').order_by('name')
        self.fields['material'].empty_label = '— Select material —'


# Inline formset: many ProcurementItems inside one ProcurementOrder
ProcurementItemFormSet = inlineformset_factory(
    ProcurementOrder,
    ProcurementItem,
    form=ProcurementItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ProcurementUpdateForm(forms.ModelForm):
    """
    Edit a Draft PO's header fields.
    Only the fields that are safe to change on a draft.
    """

    class Meta:
        model  = ProcurementOrder
        fields = ['supplier', 'order_method', 'expected_delivery_date', 'notes']
        widgets = {
            'supplier':               forms.Select(attrs=_select),
            'order_method':           forms.Select(attrs=_select),
            'expected_delivery_date': forms.DateInput(attrs=_date),
            'notes':                  forms.Textarea(attrs=_area),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Supplier.objects.filter(
            status='Active'
        ).order_by('-is_primary', 'company_name')
        self.fields['expected_delivery_date'].required = False


class ReceivingForm(forms.Form):
    """
    Filled when marking a PO as Received.

    For each ProcurementItem we generate one IntegerField named
    'received_qty_<item_pk>'. The view reads these back and
    updates each item's received_qty before calling apply_stock_in.

    Additional fields:
    - dr_number            : Delivery Receipt number from supplier
    - actual_delivery_date : The real arrival date
    - notes                : Any discrepancy comments
    """

    dr_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            **_input, 'placeholder': 'e.g., MAGNA-DR-2024-0512'
        }),
        help_text="Delivery Receipt number from the supplier"
    )
    actual_delivery_date = forms.DateField(
        widget=forms.DateInput(attrs=_date),
        help_text="Date the goods actually arrived"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            **_area,
            'placeholder': 'Note any shortages, damaged items, or substitutions...'
        })
    )

    def __init__(self, procurement_order, *args, **kwargs):
        """
        Dynamically adds one 'received_qty_<pk>' field per item.
        Pre-fills each field with the item's ordered_qty as the default
        (assuming full delivery unless the user changes it).
        """
        super().__init__(*args, **kwargs)
        self.procurement_order = procurement_order

        for item in procurement_order.items.select_related('material'):
            field_name = f'received_qty_{item.pk}'
            self.fields[field_name] = forms.IntegerField(
                min_value=0,
                max_value=item.ordered_qty,
                initial=item.ordered_qty,     # Default: full delivery
                label=item.material.name,
                widget=forms.NumberInput(attrs={
                    **_input,
                    'min': '0',
                    'max': str(item.ordered_qty),
                    'placeholder': str(item.ordered_qty),
                }),
                help_text=(
                    f"Ordered: {item.ordered_qty} {item.material.unit}. "
                    f"Enter actual quantity received (0 if none arrived)."
                )
            )