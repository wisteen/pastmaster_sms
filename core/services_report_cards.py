from decimal import Decimal

from .models import ComponentResult, ResultComponent
from .services_term_placements import report_class_for_term


def report_component_rows(student, term, results):
    """Read the assessment definitions that actually own this term's saved marks.

    Promotion changes the student's current class, not the class attached to
    historical components. Never substitute a new class's components or invent
    zero marks when the original component result is missing.
    """
    marks = list(ComponentResult.all_objects.filter(
        student=student, term=term, term__school=student.school,
        component__subject__school=student.school,
        component__school_class__school=student.school,
    ).select_related('component').order_by('component_id'))
    historical_class = report_class_for_term(student, term)
    fallback_class = historical_class.id if historical_class else None
    rows, warnings = [], []
    for result in results:
        saved = {mark.component_id: mark for mark in marks if mark.component.subject_id == result.subject_id}
        class_ids = {mark.component.school_class_id for mark in saved.values()} or {fallback_class}
        definitions = ResultComponent.all_objects.filter(
            subject=result.subject, school_class_id__in=class_ids,
            school_class__school=student.school, subject__school=student.school,
        ).order_by('id')
        components = [{
            'name': component.component_name,
            'score': saved[component.id].score if component.id in saved else None,
            'max_score': component.max_score,
            'weight': component.weight,
        } for component in definitions]
        if len(class_ids) > 1:
            warnings.append(f'{result.subject.name}: assessment marks belong to more than one class; please review.')
        if not components or any(component['score'] is None for component in components):
            warnings.append(f'{result.subject.name}: some assessment marks are not recorded. A dash means missing, not zero.')
        elif any(component['max_score'] <= 0 or component['score'] < 0 or component['score'] > component['max_score'] for component in components):
            warnings.append(f'{result.subject.name}: assessment marks or maximum marks need review.')
        else:
            weighted_total = sum(
                component['score'] * Decimal(component['weight']) / Decimal(component['max_score'])
                for component in components
            )
            if abs(weighted_total - result.total_score) > Decimal('0.05'):
                warnings.append(f'{result.subject.name}: saved total differs from the weighted assessment marks; please review.')
        rows.append({
            'subject': result.subject, 'components': components,
            'total_score': result.total_score, 'grade': result.grade, 'remark': result.remark,
        })

    # All subjects must occupy the same columns, even when their assessment
    # definitions were created in a different order or have different maxima.
    headers = []
    for row in rows:
        for component in row['components']:
            key = (component['name'], component['max_score'], component['weight'])
            if key not in headers:
                headers.append(key)
    total_obtainable = sum(component['weight'] for row in rows for component in row['components'])
    for row in rows:
        indexed = {(c['name'], c['max_score'], c['weight']): c for c in row['components']}
        row['components'] = [indexed.get(key, {
            'name': key[0], 'max_score': key[1], 'weight': key[2], 'score': None,
        }) for key in headers]
    return rows, warnings, total_obtainable


