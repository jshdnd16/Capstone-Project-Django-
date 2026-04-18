# architecture/forms.py
# Forms for the Architecture module.
#
# ProjectForm            → Create / edit a project
# BOQHeaderForm          → Create a new BOQ version header
# BOQItemForm            → One line in a BOQ
# BOQItemFormSet         → Inline formset for multiple BOQ items
# MaterialRequestForm    → Create the request header
# MaterialRequestItemForm → One material line in a request
# MaterialRequestItemFormSet → Inline formset for request items
# ApprovalForm           → Admin notes when approving or rejecting

from django import forms
from django.forms import inlineformset_factory

from .models import (
    Project, BOQHeader, BOQItem,
    MaterialRequest, MaterialRequestItem,
)
from materials.models import Material, Supplier
from accounts.models import User

# ── Shared widget helpers ─────────────────────────────────────
_input  = {'class': 'form-input'}
_select = {'class': 'form-input'}
_area   = {'class': 'form-input', 'rows': 3}
_date   = {'class': 'form-input', 'type': 'date'}


class ProjectForm(forms.ModelForm):
    """Create or edit a project."""

    class Meta:
        model  = Project
        fields = [
            'project_name', 'client_name', 'location',
            'architect', 'start_date', 'end_date',
            'status', 'budget', 'description',
        ]
        widgets = {
            'project_name': forms.TextInput(attrs={
                **_input, 'placeholder': "e.g., Lucena Residential Renovation"
            }),
            'client_name':  forms.TextInput(attrs={
                **_input, 'placeholder': "Project owner's name"
            }),
            'location':     forms.Textarea(attrs={
                **_area, 'placeholder': "Full site address in Quezon Province"
            }),
            'architect':    forms.Select(attrs=_select),
            'start_date':   forms.DateInput(attrs=_date),
            'end_date':     forms.DateInput(attrs=_date),
            'status':       forms.Select(attrs=_select),
            'budget':       forms.NumberInput(attrs={
                **_input, 'placeholder': '0.00', 'step': '0.01', 'min': '0'
            }),
            'description':  forms.Textarea(attrs={
                **_area, 'placeholder': 'Project scope, deliverables, special notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show Architect-role users in the dropdown
        self.fields['architect'].queryset = User.objects.filter(
            role__role_name__in=['Architect', 'Admin'],
            status='Active'
        ).order_by('fullname')
        self.fields['architect'].empty_label = '— Assign an Architect —'
        self.fields['budget'].required = False
        self.fields['start_date'].required = False
        self.fields['end_date'].required = False


class BOQHeaderForm(forms.ModelForm):
    """
    Creates a new BOQ version header.
    The version number is auto-incremented by the view — not editable here.
    """

    class Meta:
        model  = BOQHeader
        fields = ['notes', 'is_final']
        widgets = {
            'notes':    forms.Textarea(attrs={
                **_area,
                'placeholder': "What changed in this revision? e.g., Added roofing materials..."
            }),
            'is_final': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-mitra-gold focus:ring-mitra-gold'
            }),
        }


class BOQItemForm(forms.ModelForm):
    """One line item in a BOQ."""

    class Meta:
        model  = BOQItem
        fields = ['material', 'required_qty', 'unit_cost', 'source_type', 'supplier', 'notes']
        widgets = {
            'material':    forms.Select(attrs={**_select, 'class': 'form-input boq-material-select'}),
            'required_qty': forms.NumberInput(attrs={
                **_input, 'placeholder': '0', 'step': '0.01', 'min': '0',
                'class': 'form-input boq-qty-input',
            }),
            'unit_cost':   forms.NumberInput(attrs={
                **_input, 'placeholder': '0.00', 'step': '0.01', 'min': '0',
                'class': 'form-input boq-cost-input',
            }),
            'source_type': forms.Select(attrs=_select),
            'supplier':    forms.Select(attrs=_select),
            'notes':       forms.TextInput(attrs={**_input, 'placeholder': 'Optional note'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.filter(
            is_active=True
        ).select_related('category').order_by('name')
        self.fields['material'].empty_label = '— Select material —'
        self.fields['supplier'].queryset = Supplier.objects.filter(
            status='Active'
        ).order_by('company_name')
        self.fields['supplier'].required = False
        self.fields['supplier'].empty_label = '— External supplier (if applicable) —'
        self.fields['notes'].required = False


# Inline formset: many BOQItems inside one BOQHeader
BOQItemFormSet = inlineformset_factory(
    BOQHeader,
    BOQItem,
    form=BOQItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class MaterialRequestForm(forms.ModelForm):
    """Create a material request header."""

    class Meta:
        model  = MaterialRequest
        fields = ['project', 'fulfillment_source', 'notes']
        widgets = {
            'project':            forms.Select(attrs=_select),
            'fulfillment_source': forms.Select(attrs=_select),
            'notes': forms.Textarea(attrs={
                **_area,
                'placeholder': 'Describe urgency, site schedule, or delivery instructions...'
            }),
        }

    def __init__(self, *args, **kwargs):
        # Accept optional architect kwarg to filter projects
        self.architect = kwargs.pop('architect', None)
        super().__init__(*args, **kwargs)

        # If submitted by an Architect, show only their projects
        qs = Project.objects.filter(
            status__in=['Planning', 'Ongoing']
        ).order_by('project_name')
        if self.architect and not self.architect.is_superuser:
            role = getattr(self.architect, 'get_role_name', lambda: '')()
            if role == 'Architect':
                qs = qs.filter(architect=self.architect)
        self.fields['project'].queryset = qs
        self.fields['project'].empty_label = '— Select project —'


class MaterialRequestItemForm(forms.ModelForm):
    """One material line in a material request."""

    class Meta:
        model  = MaterialRequestItem
        fields = ['material', 'required_qty', 'unit_cost', 'source_type', 'supplier']
        widgets = {
            'material':    forms.Select(attrs={
                **_select, 'class': 'form-input mr-material-select'
            }),
            'required_qty': forms.NumberInput(attrs={
                **_input, 'placeholder': '0', 'step': '0.01', 'min': '0',
                'class': 'form-input mr-qty-input',
            }),
            'unit_cost':   forms.NumberInput(attrs={
                **_input, 'placeholder': '0.00', 'step': '0.01', 'min': '0',
                'class': 'form-input mr-cost-input',
            }),
            'source_type': forms.Select(attrs=_select),
            'supplier':    forms.Select(attrs=_select),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['material'].queryset = Material.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['material'].empty_label = '— Select material —'
        self.fields['supplier'].queryset = Supplier.objects.filter(
            status='Active'
        ).order_by('company_name')
        self.fields['supplier'].required = False
        self.fields['supplier'].empty_label = '— External supplier —'


MaterialRequestItemFormSet = inlineformset_factory(
    MaterialRequest,
    MaterialRequestItem,
    form=MaterialRequestItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class ApprovalForm(forms.Form):
    """
    Simple form for Admin to add notes when approving or rejecting
    a material request. The action (approve/reject) comes from which
    submit button was clicked, not from this form.
    """
    admin_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            **_area,
            'placeholder': 'Optional: explain approval conditions or rejection reason...'
        })
    )


class FulfillmentForm(forms.Form):
    """
    Used when Warehouse/Admin records actual quantities issued
    for each item on an approved material request.
    Rendered dynamically in the view — one field per request item.
    """
    pass   # Fields are added dynamically in the view