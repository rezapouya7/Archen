from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def csp_nonce(context):
    """Return the request's CSP nonce value if available, else empty string.

    Usage in templates:
      <script nonce="{% csp_nonce %}">...</script>
    or with the attr helper:
      <script{% csp_nonce_attr %}>...</script>
    """
    req = context.get('request')
    return getattr(req, 'csp_nonce', '') if req else ''


@register.simple_tag(takes_context=True, name='csp_nonce_attr')
def csp_nonce_attr(context):
    """Render nonce attribute if available, else an empty string.

    Produces: ' nonce="<nonce>"' when request has a csp_nonce.
    """
    nonce = csp_nonce(context)
    return f' nonce="{nonce}"' if nonce else ''

