# PATH: /Archen/production_line/utils.py
from typing import Optional
from django.contrib.auth.models import Group
from .models import ROLE_TO_SECTION, SectionChoices
PERSIAN_ROLE_TO_SLUG = {
    # Managers and accounting
    "مدیر": "manager",
    "حسابدار": "accountant",
    # Workshop roles
    "برش‌کار": "cutter_master",
    "استاد برش": "cutter_master",  # Support old titles
    "سی‌ان‌سی‌کار": "cnc_master",
    "استاد سی‌ان‌سی": "cnc_master",  # Previous titles
    "مونتاژ‌کار": "assembly_master",
    "استاد مونتاژ": "assembly_master",
    "نقاش زیرکار‌ رنگ": "undercoating_master",
    "استاد زیرکار رنگ": "undercoating_master",
    "نقاش رنگ": "painting_master",
    "استاد رنگ‌کار": "painting_master",
    "صفحه‌کار": "workpage_master",
    # Sewing and upholstery map to the same section in the production line
    "خیاط": "sewing_master",
    "استاد خیاط": "sewing_master",
    "رویه‌کوب‌کار": "upholstery_master",
    "استاد رویه‌کوبی": "upholstery_master",
    "مسئول بسته‌بندی": "packaging_master",
    # Sales role is outside of the production line
    "مسئول فروش": None,
}

KNOWN_SLUGS = {
    'cutter_master', 'cnc_master', 'undercoating_master', 'painting_master',
    'assembly_master', 'sewing_master', 'upholstery_master', 'workpage_master',
    'packaging_master', 'accountant', 'manager', 'seller'
}


def canonical_role(value: Optional[str]) -> Optional[str]:
    """Normalize a Persian or slug role string to canonical slug."""
    if not value:
        return None
    s = str(value).strip()
    if s in KNOWN_SLUGS:
        return s
    return PERSIAN_ROLE_TO_SLUG.get(s, None)


def get_user_role(user) -> Optional[str]:
    """
    Resolve user's role robustly:
    1) Use user.role (may be Persian or slug).
    2) Fall back to Django Groups with Persian names (e.g., 'مدیر', 'خط تولید' -> None).
    """
    # 1) direct role field
    role = canonical_role(getattr(user, "role", None))
    if role is not None:
        return role

    # 2) try groups
    try:
        for g in Group.objects.filter(user=user):
            cand = canonical_role(g.name)
            if cand is not None:
                return cand
    except Exception:
        pass

    return None


def role_to_section(role: Optional[str]):
    """Map canonical role to SectionChoices (None for manager/invalid)."""
    if role == "manager":
        return None
    return ROLE_TO_SECTION.get(role, None)


def is_parts_based(section: Optional[str]) -> bool:
    return section in (SectionChoices.CUTTING, SectionChoices.CNC_TOOLS)


def is_products_based(section: Optional[str]) -> bool:
    return section in (
        SectionChoices.ASSEMBLY,
        SectionChoices.UNDERCOATING,
        SectionChoices.PAINTING,
        SectionChoices.WORKPAGE,
        SectionChoices.SEWING,
        SectionChoices.UPHOLSTERY,
        SectionChoices.PACKAGING,
    )


def _normalize_material_name(value: str) -> str:
    """Normalize a material/part name for fuzzy Persian comparisons."""
    if not value:
        return ""
    text = str(value).strip().lower()
    translation_table = str.maketrans({
        'ي': 'ی',
        'ك': 'ک',
    })
    text = text.translate(translation_table)
    for ch in ('‌', '-', '_', '.', '/', '\\'):
        text = text.replace(ch, ' ')
    return ' '.join(text.split())


def contains_mdf_page_material(value: str) -> bool:
    """Return True if the value contains the phrase 'صفحه ام‌دی‌اف' (with variations)."""
    normalized = _normalize_material_name(value)
    if not normalized:
        return False
    collapsed = normalized.replace(' ', '')
    return 'صفحهامدیاف' in collapsed


def product_contains_mdf_page(product) -> bool:
    """
    Check whether the product's material BOM includes an entry labeled 'صفحه ام‌دی‌اف'.

    The detection only inspects the materials list per business rules.  It gracefully
    handles prefetched relations as well as direct ORM lookups.
    """
    if not product:
        return False

    def _yield_material_rows():
        relation = getattr(product, 'material_bom_items', None)
        if relation is not None:
            try:
                for row in relation.all():
                    yield row
                return
            except Exception:
                try:
                    for row in relation:
                        yield row
                    return
                except TypeError:
                    pass
        try:
            from inventory.models import ProductMaterial
            for row in ProductMaterial.objects.filter(product=product).select_related('material'):
                yield row
        except Exception:
            return

    for row in _yield_material_rows():
        material = getattr(row, 'material', None)
        candidate = getattr(material, 'name', '') if material else getattr(row, 'material_name', '')
        if contains_mdf_page_material(candidate):
            return True

    return False
