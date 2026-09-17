from django import template

register = template.Library()


@register.filter
def money(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return value
    return f'{amount:,.2f}'
