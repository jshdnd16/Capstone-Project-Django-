# procurement/templatetags/form_extras.py
# Custom template filters for rendering dynamic form fields.

from django import template

register = template.Library()


@register.filter
def get_field(form, field_name):
    """
    Renders a specific named field from a form.
    Usage: {{ form|get_field:"field_name" }}
    
    Used in procurement_receive_form.html to render dynamically
    generated received_qty_<pk> fields.
    """
    try:
        return form[field_name]
    except KeyError:
        return ''


@register.filter
def get_item(dictionary, key):
    """
    Gets a value from a dictionary by key.
    Usage: {{ dict|get_item:"key" }}
    
    Used to access form field errors by dynamic field name.
    """
    return dictionary.get(key, [])


@register.filter
def get_help_text(form, field_name):
    """
    Returns the help_text for a specific form field.
    Usage: {{ form|get_help_text:"field_name" }}
    """
    try:
        return form.fields[field_name].help_text
    except KeyError:
        return ''