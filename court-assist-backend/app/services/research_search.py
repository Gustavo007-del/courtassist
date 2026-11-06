SEARCH_COLUMNS = (
    "title",
    "case_title",
    "citation",
    "court",
    "case_number",
    "cnr_number",
    "act_name",
    "section_number",
    "subject",
    "source_name",
    "summary",
    "full_text",
    "notes",
)
SEARCH_SQL = " || ' ' || ".join("coalesce(" + name + ", '')" for name in SEARCH_COLUMNS)
