from django import template

register = template.Library()


@register.filter
def split_lines(value):
    """Divide um TextField em lista de linhas não-vazias."""
    if not value:
        return []
    return [line.strip() for line in value.splitlines() if line.strip()]


@register.filter
def count_lines(value):
    """Conta linhas não-vazias de um TextField."""
    if not value:
        return 0
    return sum(1 for line in value.splitlines() if line.strip())
