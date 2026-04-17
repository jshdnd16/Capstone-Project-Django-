# sales/forms.py
# Forms for the Sales module.
#
# ClientForm        → Create / edit a client record
# OrderForm         → Create the order header (client, type, notes)
# OrderItemForm     → A single line item (material + qty)
# OrderItemFormSet  → Multiple line items on one page (inline formset)
# PaymentStatusForm → Lightweight form just for updating payment status
# OrderStatusForm   → Lightweight form just for advancing the order status

from django import forms
from django.forms import inlineformset_factory

from .models import Client, Order, OrderItem
from materials.models import Material

# ── Shared CSS helpers ────────────────────────────────────────
_input  = {'class': 'form-input'}
_select = {'class': 'form-input'}
_area   = {'class': 'form-input', 'rows': 3}


class ClientForm(forms.ModelForm):
    """Create or edit a client (hardware store, walk-in, contractor)."""

    class Meta:
        model  = Client
        fields = [
            'client_name', 'contact_person', 'phone',
            'address', 'client_type', 'delivery_zone', 'notes', 'is_active',
        ]
        widgets = {
            'client_name':    forms.TextInput(attrs={**_input, 'placeholder': 'e.g., Buildrite Hardware Tiaong'}),
            'contact_person': forms.TextInput(attrs={**_input, 'placeholder': 'Owner or manager name'}),
            'phone':          forms.TextInput(attrs={**_input, 'placeholder': '09XX-XXX-XXXX'}),
            'address':        forms.Textarea(attrs={**_area,   'placeholder': 'Store / delivery address'}),
            'client_type':    forms.Select(attrs=_select),
            'delivery_zone':  forms.Select(attrs=_select),
            'notes':          forms.Textarea(attrs={**_area, 'placeholder': 'Credit terms, special instructions...'}),
            'is_active':      forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-mitra-gold focus:ring-mitra-gold'
            }),
        }


class OrderForm(forms.ModelForm):
    """
    Creates the Order header — client, type, and notes.
    Items are added separately via OrderItemFormSet on the same page.
    """

    class Meta:
        model  = Order
        fields = ['client', 'order_type', 'payment_status', 'notes']
        widgets = {
            'client':         forms.Select(attrs=_select),
            'order_type':     forms.Select(attrs=_select),
            'payment_status': forms.Select(attrs=_select),
            'notes':          forms.Textarea(attrs={**_area, 'placeholder': 'Delivery notes, special requests...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active clients in the dropdown
        self.fields['client'].queryset = Client.objects.filter(
            is_active=True
        ).order_by('client_name')
        # Add a helpful empty label
        self.fields['client'].empty_label = '— Select a client —'


class OrderItemForm(forms.ModelForm):
    """
    A single line item inside an order.
    
    When rendered in a formset, many of these appear on one page,
    one row per material ordered.
    """

    class Meta:
        model  = OrderItem
        fields = ['material', 'quantity', 'price_at_sale']
        widgets = {
            'material':     forms.Select(attrs={
                **_select,
                'class': 'form-input material-select',   # Extra class for JS hook
            }),
            'quantity':     forms.NumberInput(attrs={
                **_input, 'placeholder': '1', 'min': '1',
                'class': 'form-input qty-input',
            }),
            'price_at_sale': forms.NumberInput(attrs={
                **_input, 'placeholder': '0.00', 'step': '0.01', 'min': '0',
                'class': 'form-input price-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only offer active materials in the material dropdown
        self.fields['material'].queryset = Material.objects.filter(
            is_active=True
        ).select_related('category').order_by('name')
        self.fields['material'].empty_label = '— Select material —'
        self.fields['price_at_sale'].required = True


# ─────────────────────────────────────────────────────────────
# INLINE FORMSET
# Renders multiple OrderItemForms together on one page.
# extra=1  → always show 1 blank row for adding the first/next item
# can_delete=True → show a delete checkbox on each row
# ─────────────────────────────────────────────────────────────
OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,          # At least one item is required
    validate_min=True,
)


class PaymentStatusForm(forms.ModelForm):
    """
    Lightweight form used only for the payment status update widget
    on the order detail page — keeps the update focused.
    """

    class Meta:
        model  = Order
        fields = ['payment_status']
        widgets = {
            'payment_status': forms.Select(attrs=_select),
        }
    

class OrderNotesForm(forms.ModelForm):
    """Update only the order notes field."""

    class Meta:
        model  = Order
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={**_area, 'placeholder': 'Add or update notes...'}),
        }