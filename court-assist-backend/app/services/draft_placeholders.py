"""Expand only supplied or owned workspace values, preserving missing placeholders."""
import re

PLACEHOLDER = re.compile(r'\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}')

def expand(content, values):
    missing=set()
    def replace(match):
        key=match.group(1)
        value=values.get(key)
        if value is None or str(value)=='':
            missing.add(key)
            return match.group(0)
        return str(value)
    result=PLACEHOLDER.sub(replace,content)
    return {'content':result,'missing_placeholders':sorted(missing),'values':values}

def workspace_values(user,client=None,case=None):
    values={'advocate.name':user.full_name,'advocate.address':user.office_address or user.address,
            'advocate.phone':user.office_phone or user.phone_number,'advocate.email':user.professional_email or user.email,
            'advocate.enrollment_number':user.enrollment_number,'advocate.designation':user.professional_designation,
            'hearing.date':None,'document.date':None,'document.content':None}
    if client:
        values.update({'client.name':client.full_name,'client.address':client.address,'client.phone':client.phone_number,'client.email':client.email})
    if case:
        values.update({'case.number':case.case_number,'case.cnr':case.cnr_number,'case.title':case.case_title,
                       'case.type':case.case_type,'case.filing_date':str(case.filing_date),
                       'court.name':case.court.name if case.court else None,
                       'court.location':case.court.address if case.court else None,
                       'petitioner.details':'; '.join(p.party_name+' · '+p.address for p in case.parties if p.party_role.strip().lower() in ('petitioner','petitioners')) or None,
                       'respondent.details':'; '.join(p.party_name+' · '+p.address for p in case.parties if p.party_role.strip().lower() in ('respondent','respondents')) or None,
                       'party.names':'; '.join(p.party_name for p in case.parties),
                       'party.roles':'; '.join(f'{p.party_name}: {p.party_role}' for p in case.parties)})
    return values
