from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, create_model, field_validator

Text = Annotated[str, Field(max_length=200000)]
Title = Annotated[str, Field(min_length=1, max_length=180)]
Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)]

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class TemplateInput(Input):
    name: Title
    category: Annotated[str, Field(max_length=80)] = 'Other'
    description: Text = ''
    content: Text = ''
    active: bool = True

class DraftInput(Input):
    title: Title
    content: Text = ''
    status: Literal['draft','review','final'] = 'draft'
    case_id: UUID | None = None
    client_id: UUID | None = None
    template_id: UUID | None = None
    category: Annotated[str, Field(min_length=1,max_length=80)] = 'General legal documents'
    language: Literal['en','ml'] = 'en'

class ClauseInput(Input):
    title: Title
    category: Annotated[str, Field(max_length=80)] = 'General'
    content: Text
    tags: list[Annotated[str, Field(min_length=1,max_length=60)]] = Field(default_factory=list,max_length=30)

class AgreementInput(Input):
    client_id: UUID
    case_id: UUID | None = None
    amount: Money
    currency: Literal['INR'] = 'INR'
    fee_type: Annotated[str, Field(max_length=40)] = 'fixed'
    description: Text = ''
    agreement_date: date = Field(default_factory=date.today)
    due_date: date | None = None
    status: Literal['draft','active','completed','closed','cancelled'] = 'active'
    title: Annotated[str,Field(max_length=180)]=''
    payment_terms: Annotated[str,Field(max_length=5000)]=''
    notes: Annotated[str,Field(max_length=5000)]=''

class PaymentInput(Input):
    client_id: UUID
    case_id: UUID | None = None
    agreement_id: UUID | None = None
    amount: Money
    currency: Literal['INR'] = 'INR'
    payment_date: date = Field(default_factory=date.today)
    method: Annotated[str, Field(min_length=1,max_length=40)] = 'UPI'
    status: Literal['pending','received','failed','cancelled'] = 'pending'
    reference: Annotated[str, Field(max_length=120)] = ''
    description: Annotated[str,Field(max_length=5000)]=''
    notes: Annotated[str,Field(max_length=5000)]=''

class ExpenseInput(Input):
    client_id: UUID | None = None
    case_id: UUID | None = None
    amount: Money
    currency: Literal['INR'] = 'INR'
    expense_date: date = Field(default_factory=date.today)
    category: Annotated[str, Field(max_length=80)] = 'Other'
    description: Text = ''
    payment_method: Annotated[str,Field(max_length=40)]='Cash'
    vendor: Annotated[str,Field(max_length=180)]=''
    reference: Annotated[str,Field(max_length=120)]=''
    notes: Annotated[str,Field(max_length=5000)]=''
    document_id: UUID|None=None
    status: Literal['draft','confirmed']='confirmed'

class ResearchInput(Input):
    title: Title
    item_type: Annotated[str, Field(max_length=60)] = 'note'
    citation: Annotated[str, Field(max_length=240)] = ''
    court: Annotated[str, Field(max_length=180)] = ''
    subject: Annotated[str, Field(max_length=180)] = ''
    source_url: HttpUrl | None = None
    source_status: Literal['unverified','manually_entered','document_extracted'] = 'unverified'
    summary: Text = ''
    notes: Text = ''
    tags: list[Annotated[str, Field(min_length=1,max_length=60)]] = Field(default_factory=list,max_length=30)
    case_id: UUID | None = None

    @field_validator('source_url',mode='before')
    @classmethod
    def empty_url(cls,value):
        return value or None

class RestoreInput(Input):
    version_id: UUID

# Missing patch fields retain stored values; explicit null is validated after merging.
def patch_schema(name, schema):
    return create_model(name, __base__=Input, **{key:(field.annotation | None, None) for key,field in schema.model_fields.items()})

TemplatePatch=patch_schema('TemplatePatch',TemplateInput)
DraftPatch=patch_schema('DraftPatch',DraftInput)
DraftPatch=create_model('DraftPatchWithRevision',__base__=DraftPatch,expected_updated_at=(datetime|None,None))
ClausePatch=patch_schema('ClausePatch',ClauseInput)
ResearchPatch=patch_schema('ResearchPatch',ResearchInput)
