# materials/forms.py
# Django forms handle both rendering AND validation for our three models.
# We add CSS classes here so they match the existing form-input style.

from django import forms
from .models import Category, Supplier, Material


class CategoryForm(forms.ModelForm):
    """Simple form for creating or editing a category."""

    class Meta:
        model = Category
        fields = ['category_name', 'description']
        widgets = {
            'category_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Construction Chemicals, Paints & Coatings',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Brief description of this category...',
            }),
        }


class SupplierForm(forms.ModelForm):
    """Form for creating or editing a supplier."""

    class Meta:
        model = Supplier
        fields = [
            'company_name', 'contact_person', 'phone', 'email',
            'address', 'supplier_type', 'status', 'is_primary',
        ]
        widgets = {
            'company_name':   forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Company name'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contact person'}),
            'phone':          forms.TextInput(attrs={'class': 'form-input', 'placeholder': '09XX-XXX-XXXX'}),
            'email':          forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'email@company.com'}),
            'address':        forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Full address'}),
            'supplier_type':  forms.Select(attrs={'class': 'form-input'}),
            'status':         forms.Select(attrs={'class': 'form-input'}),
            'is_primary':     forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-mitra-gold focus:ring-mitra-gold'
            }),
        }


class MaterialForm(forms.ModelForm):
    """
    Form for creating or editing a material.
    
    Custom __init__ filters the supplier dropdown to only show Active suppliers,
    and custom clean() ensures selling_price > current_cost.
    """

    class Meta:
        model = Material
        fields = [
            'sku', 'name', 'category', 'supplier', 'unit',
            'current_cost', 'selling_price', 'reorder_level',
            'is_sales_inventory', 'is_active',
        ]
        widgets = {
            'sku':              forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Optional: e.g., BW-001'}),
            'name':             forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., Buildrite Waterproofing 20kg'}),
            'category':         forms.Select(attrs={'class': 'form-input'}),
            'supplier':         forms.Select(attrs={'class': 'form-input'}),
            'unit':             forms.Select(attrs={'class': 'form-input'}),
            'current_cost':     forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'selling_price':    forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '0.00', 'step': '0.01', 'min': '0'}),
            'reorder_level':    forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '10', 'min': '0'}),
            'is_sales_inventory': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-mitra-gold focus:ring-mitra-gold'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-mitra-gold focus:ring-mitra-gold'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show Active suppliers in the dropdown — no point showing inactive ones
        self.fields['supplier'].queryset = Supplier.objects.filter(status='Active').order_by('company_name')
        # SKU is optional
        self.fields['sku'].required = False

    def clean(self):
        """
        Form-level validation that runs after individual field validation.
        Checks that selling price is not lower than cost price — that would mean selling at a loss.
        """
        cleaned_data = super().clean()
        cost = cleaned_data.get('current_cost')
        price = cleaned_data.get('selling_price')

        if cost is not None and price is not None and price < cost:
            raise forms.ValidationError(
                f"Selling price (₱{price}) cannot be lower than cost price (₱{cost}). "
                "Please check your values."
            )
        return cleaned_data