# accounts/utils.py
# Helper utility functions used throughout the project.
# The most important one here is `log_action()` — call this
# whenever something important happens in the system.

from .models import TransactionLog


def log_action(user, action_type, table_affected='', record_id=None,
               description='', request=None):
    """
    Creates an audit log entry in the TransactionLog table.
    
    Call this function every time a significant action occurs.
    
    Parameters:
    - user           : The User object performing the action
    - action_type    : String like 'CREATE_ORDER', 'LOGIN', etc.
    - table_affected : Which model/table was affected (e.g. 'orders')
    - record_id      : The primary key of the affected record
    - description    : Human-readable description of what happened
    - request        : The HTTP request (used to extract IP address)
    
    Example usage in a view:
        log_action(
            user=request.user,
            action_type='CREATE_ORDER',
            table_affected='orders',
            record_id=order.pk,
            description=f"Created order #{order.pk} for {order.client}",
            request=request
        )
    """

    # Extract the user's IP address from the request, if available
    ip_address = None
    if request:
        # Check for proxy headers first (common in production setups)
        x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded:
            # X-Forwarded-For can have multiple IPs — the first is the real client
            ip_address = x_forwarded.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')

    # Create the log entry in the database
    TransactionLog.objects.create(
        user=user,
        action_type=action_type,
        table_affected=table_affected,
        record_id=record_id,
        description=description,
        ip_address=ip_address,
    )


def get_client_ip(request):
    """
    Extracts the real IP address from an HTTP request.
    Handles cases where the app is behind a proxy/load balancer.
    """
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')