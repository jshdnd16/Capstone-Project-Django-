# delivery/forms.py
# Three forms for the delivery module:
#
# DeliveryCreateForm    → Schedule a new delivery (Sales or Architecture)
# DeliveryUpdateForm    → Edit scheduling details before departure
# StatusUpdateForm      → Advance the delivery status (with optional notes)
#                         Used by both Drivers and Sales/Admin
# CompletionForm        → Record DR number, received_by, and delay info
#                         when marking a delivery as Received

from django import forms
from django.contrib.auth import get_user_model

from .models import Delivery
from sales.models import Order
from architecture.models import MaterialRequest

User = get_user_model()

# Shared CSS helpers
_input  = {'class': 'form-input'}
_select = {'class': 'form-input'}
_area   = {'class': 'form-input', 'rows': 3}
_date   = {'class': 'form-input', 'type': 'date'}
_check  = {'class': 'h-4 w-4 rounded border-gray-300 text-mitra-gold focus:ring-mitra-gold'}


class DeliveryCreateForm(forms.ModelForm):
    """
    Schedules a new delivery.

    delivery_type controls which source dropdown is shown — the
    other one is hidden by JavaScript on the frontend.

    Either order OR request must be provided; the clean() method
    enforces this and also validates that the source document is
    in an appropriate status for delivery.
    """

    class Meta:
        model  = Delivery
        fields = [
            'delivery_type',
            'order', 'request',
            'driver', 'driver_name', 'delivery_team', 'vehicle_plate',
            'schedule_date',
            'start_location', 'end_location', 'route_notes',
            'notes',
        ]
        widgets = {
            'delivery_type':  forms.Select(attrs=_select),
            'order':          forms.Select(attrs={**_select, 'id': 'id_order'}),
            'request':        forms.Select(attrs={**_select, 'id': 'id_request'}),
            'driver':         forms.Select(attrs=_select),
            'driver_name':    forms.TextInput(attrs={**_input, 'placeholder': 'Full name of driver'}),
            'delivery_team':  forms.Select(attrs=_select),
            'vehicle_plate':  forms.TextInput(attrs={**_input, 'placeholder': 'e.g., ABC 1234'}),
            'schedule_date':  forms.DateInput(attrs=_date),
            'start_location': forms.TextInput(attrs={**_input, 'placeholder': 'Warehouse / hub address'}),
            'end_location':   forms.TextInput(attrs={**_input, 'placeholder': 'Hardware store or project site'}),
            'route_notes':    forms.Textarea(attrs={**_area, 'placeholder': 'Directions, landmarks...'}),
            'notes':          forms.Textarea(attrs={**_area, 'placeholder': 'Special instructions...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only show orders that are in Preparing or Out for Delivery status
        # (i.e. goods are ready to ship)
        self.fields['order'].queryset = Order.objects.filter(
            status__in=['Preparing', 'Out for Delivery']
        ).select_related('client').order_by('-order_date')
        self.fields['order'].empty_label  = '— Select Sales Order —'
        self.fields['order'].required     = False

        # Only show approved / partially fulfilled material requests
        self.fields['request'].queryset = MaterialRequest.objects.filter(
            status__in=['Approved', 'Partially Fulfilled']
        ).select_related('project').order_by('-request_date')
        self.fields['request'].empty_label = '— Select Material Request —'
        self.fields['request'].required    = False

        # Only show Driver-role users in the driver dropdown
        self.fields['driver'].queryset = User.objects.filter(
            role__role_name='Driver',
            status='Active'
        ).order_by('fullname')
        self.fields['driver'].empty_label = '— Assign a driver (optional) —'
        self.fields['driver'].required    = False

    def clean(self):
        """
        Ensures that exactly one source document is provided
        and that it matches the selected delivery_type.
        """
        cleaned = super().clean()
        dtype   = cleaned.get('delivery_type')
        order   = cleaned.get('order')
        request = cleaned.get('request')

        if dtype == 'Sales Order' and not order:
            raise forms.ValidationError(
                "Please select a Sales Order for a Sales Order delivery."
            )
        if dtype == 'Architecture Request' and not request:
            raise forms.ValidationError(
                "Please select a Material Request for an Architecture delivery."
            )

        # Clear the unused field so it's not saved accidentally
        if dtype == 'Sales Order':
            cleaned['request'] = None
        else:
            cleaned['order'] = None

        # Auto-fill driver_name from the selected driver User if blank
        driver      = cleaned.get('driver')
        driver_name = cleaned.get('driver_name', '').strip()
        if driver and not driver_name:
            cleaned['driver_name'] = driver.fullname

        return cleaned


class DeliveryUpdateForm(forms.ModelForm):
    """
    Edit scheduling details (date, location, driver, vehicle) before departure.
    Only available while status is still 'Scheduled'.
    """

    class Meta:
        model  = Delivery
        fields = [
            'driver', 'driver_name', 'delivery_team', 'vehicle_plate',
            'schedule_date', 'start_location', 'end_location',
            'route_notes', 'notes',
        ]
        widgets = {
            'driver':         forms.Select(attrs=_select),
            'driver_name':    forms.TextInput(attrs=_input),
            'delivery_team':  forms.Select(attrs=_select),
            'vehicle_plate':  forms.TextInput(attrs=_input),
            'schedule_date':  forms.DateInput(attrs=_date),
            'start_location': forms.TextInput(attrs=_input),
            'end_location':   forms.TextInput(attrs=_input),
            'route_notes':    forms.Textarea(attrs=_area),
            'notes':          forms.Textarea(attrs=_area),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['driver'].queryset = User.objects.filter(
            role__role_name='Driver', status='Active'
        ).order_by('fullname')
        self.fields['driver'].required     = False
        self.fields['driver'].empty_label  = '— Assign driver —'


class StatusUpdateForm(forms.Form):
    """
    Advances the delivery to the next status.
    Used by both the Driver (mobile view) and Sales/Admin (office view).
    The new_status is passed as a hidden field from the template button.
    """
    new_status = forms.CharField(widget=forms.HiddenInput())
    notes      = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            **_area,
            'placeholder': 'Optional: describe what happened at this step...',
        })
    )


class CompletionForm(forms.ModelForm):
    """
    Filled in when marking a delivery as 'Received'.
    Records the Delivery Receipt number, who signed, and any delays.
    """

    class Meta:
        model  = Delivery
        fields = [
            'dr_number', 'received_by',
            'weather_delay', 'driver_unavailable_delay', 'closed_store_delay',
            'delay_remarks',
        ]
        widgets = {
            'dr_number':   forms.TextInput(attrs={
                **_input, 'placeholder': 'e.g., DR-2024-0512'
            }),
            'received_by': forms.TextInput(attrs={
                **_input, 'placeholder': 'Name of person who received / signed'
            }),
            'weather_delay':           forms.CheckboxInput(attrs=_check),
            'driver_unavailable_delay': forms.CheckboxInput(attrs=_check),
            'closed_store_delay':       forms.CheckboxInput(attrs=_check),
            'delay_remarks': forms.Textarea(attrs={
                **_area,
                'placeholder': 'Describe delays, issues, or anything noteworthy...'
            }),
        }