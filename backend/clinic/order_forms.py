"""Definitions for the pre-printed ward ordering forms.

Two Mater Dei stock forms are reproduced faithfully in the app so the stoma
team can fill them in and send them straight to Disposables & Supplies:

  * mmml-topup    — M.M.M.U. IRO Top-Up System List (Disposables), STO-01
  * cleaning      — Cleaning Consumables Order List

Each definition carries the pre-printed item rows (transcribed from the
original spreadsheets), the column layout used to render and email the form,
and where it is sent. The rows are stored data, not a migration: a submitted
form is saved as an OrderingDocument with these values in its ``items`` JSON.
"""

# Every ward ordering form here is processed by the same office.
DISPOSABLES_EMAIL = "disposablessupplies.mdh@gov.mt"


# --- M.M.M.U. IRO Top-Up System List (Disposables) — pre-printed items ------
TOPUP_ITEMS = [
    {"code": "P2019", "description": "ALCOHOL WIPES", "topup": "2"},
    {"code": "EQ02050", "description": "BASIC DRESSING PACK STERILE", "topup": "18"},
    {"code": "F011", "description": "DRESSING STERILE - HYDROCOLLOID 10CM X 10CM", "topup": "5"},
    {"code": "F012", "description": "DRESSING STERILE - HYDROCOLLOID 20CM X 20CM", "topup": "5"},
    {"code": "F027", "description": "DRESSING STERILE - HYDROCOLLOID THIN FILM 5CM X 20CM", "topup": "5"},
    {"code": "EQ07023", "description": "GLOVES - HYPOALLERGENIC LATEX EXAM SIZE MEDIUM", "topup": "200"},
    {"code": "ICU014", "description": "GLOVES - HYPOALLERGENIC LATEX EXAM SIZE LARGE", "topup": "200"},
    {"code": "EQ02033", "description": "LOW ADHERENT DRESSING STERILE - 5CM X 5CM", "topup": "5"},
    {"code": "EQ12036", "description": "LANCET - BLOOD", "topup": "50"},
    {"code": "EQ13096", "description": "GLUCOSE IN BLOOD MONITORING STRIPS", "topup": "200"},
    {"code": "EQ17019", "description": "REMOVAL OF SUTURE PACK STERILE", "topup": "1"},
    {"code": "EQ02037", "description": "SELF ADHESIVE FABRIC  ROLL - 10CM X 10M", "topup": "1"},
    {"code": "EQ02038", "description": "SELF ADHESIVE FABRIC ROLL - 15CM X 10M", "topup": "1"},
    {"code": "EQ02013", "description": "SWAB DISP NON WOVEN STERILE . 10 X 10", "topup": "225"},
    {"code": "EQ03004", "description": "TAPE - HYPOALLERGIC SURGICAL", "topup": "1"},
    {"code": "ICU025", "description": "SANITIZING WIPES (CLINELL SURFACE WIPES)", "topup": "1"},
    {"code": "EQ13534", "description": "SURGICAL HAIR CLIPPER BLADE", "topup": "4"},
    {"code": "P2020", "description": "ALCOHOL HAND RUB", "topup": "1"},
    {"code": "P3021", "description": "SKIN CARE LOTION HIGH QUALITY NON - GREASY MOISTURIZING PERFUME FREE 500ML", "topup": "1"},
    {"code": "EQ16162", "description": "ADHESIEVE REMOVER SPRAY", "topup": "2"},
    {"code": "MASK005", "description": "MASK FACE", "topup": "50"},
]

# --- Cleaning Consumables Order List — pre-printed items --------------------
CLEANING_ITEMS = [
    {"code": "10FOIL-005", "description": "ALUMINIUM FOIL", "unit": "PACK"},
    {"code": "15APRON015", "description": "APRONS DISPOSABLE APRONS FOR DISPENSERERS", "unit": "Number"},
    {"code": "11BAGS-070", "description": "BAGS HOT WATER SOLUBLE", "unit": "BAGS"},
    {"code": "11BAGS-040", "description": "BAGS PLASTIC CLEAR W/RED HD 165 X 230 X 25 (F/BLOOD SAMPLES)", "unit": "BAGS"},
    {"code": "11BAGS-080", "description": "BAGS PLASTIC CLEAR 19\" X 21\" W/MDH PRINT", "unit": ""},
    {"code": "11BAGS-062", "description": "BAGS REFUSE TRANSPARENT 32\" X 40\" FOR DOMESTIC WASTE ONLY", "unit": "BAGS"},
    {"code": "11BAGS-050", "description": "BAGS REFUSE YELLOW 32\" X 40\" FOR BIOHAZARD", "unit": "BAGS"},
    {"code": "11BAGS-065", "description": "BAGS VOMITING 123mm X 80mm X 237mm", "unit": "BAGS"},
    {"code": "01BINS002", "description": "BINS", "unit": "NUMBER"},
    {"code": "CC-BLADE-001", "description": "BLADES FOR SAFETY RAZORS", "unit": ""},
    {"code": "01BOWLS007", "description": "BOWLS DISPOSABLE", "unit": "NUMBER"},
    {"code": "15BRACE010", "description": "BRACELETS IDENTIFICATION ADULT", "unit": "Number"},
    {"code": "15BRACE020", "description": "BRACELETS IDENTIFICATION ADULT ALLERGY RED", "unit": "Number"},
    {"code": "15BRACE005", "description": "BRACELETS IDENTIFICATION PAEDIATRIC", "unit": "Number"},
    {"code": "15BRACE015", "description": "BRACELETS IDENTIFICATION PAEDIATRIC ALLERGY RED", "unit": "Number"},
    {"code": "03BROOM015", "description": "BROOM FIBRE", "unit": "Number"},
    {"code": "03BRUSH015", "description": "BRUSHES SCRUBBING", "unit": "Number"},
    {"code": "03BRUSH005", "description": "BRUSHES FOR BOTTLES", "unit": "Number"},
    {"code": "15CAPS-015", "description": "CAPS FOR FEMALE NURSES ITEM A FOR LONG HAIR", "unit": "Number"},
    {"code": "15CAPS-005", "description": "CAPS FOR FEMALE NURSES ITEM B FOR SHORT HAIR", "unit": "Number"},
    {"code": "15CAPS-010", "description": "CAPS FOR MALE NURSES", "unit": "Number"},
    {"code": "03CLOTH005", "description": "CLOTH  KITCHEN", "unit": "Number"},
    {"code": "03DETER020", "description": "DETERGENT FLOOR X 5 LTRS", "unit": "LTRS."},
    {"code": "03DETER025", "description": "DISH WASHING LIQUID X 5 LITRES", "unit": "LTRS."},
    {"code": "01ENDM005", "description": "ENDS FOR COTTON MOPS 400gr", "unit": "Number"},
    {"code": "15MASKS005", "description": "FACE MASKS DISPOSABLE C/W FILTER", "unit": "Number"},
    {"code": "15FOAMS005", "description": "FOAM SHAVING", "unit": ""},
    {"code": "", "description": "FRENCH MOPS COMPLETE (60 WIDE)", "unit": "Number"},
    {"code": "", "description": "FRENCH MOPS COMPLETE (40 WIDE)", "unit": "Number"},
    {"code": "03POLIS", "description": "FURNITURE POLISH", "unit": "Number"},
    {"code": "03CLEAN020", "description": "GLASS CLEANING LIQUID X 1000ML", "unit": "Number"},
    {"code": "03GLOVE005", "description": "GLOVES RUBBER HOUSEHOLD", "unit": "LARGE"},
    {"code": "15GOWNS005", "description": "GOWNS PLASTIC DISPOSABLE", "unit": "Number"},
    {"code": "03DETER075", "description": "HAND & BODY WASH X 3.78 LTRS (F/OUTPATIENTS ONLY)", "unit": "LTRS."},
    {"code": "03DETER030", "description": "HAND & BODY WASH X 5 LTRS", "unit": "LTRS."},
    {"code": "03DETER032", "description": "HAND & BODY WASH X 500ML C/W DISPENSER PUMP (F/WARDS ONLY)", "unit": "BOTTLES"},
    {"code": "03DETER105", "description": "HAND WASH SERAMAN SENSITIVE 1000ml", "unit": ""},
    {"code": "01HANDL005", "description": "HANDLES ALUMINUIM FOR MOPS", "unit": "Number"},
    {"code": "", "description": "HYGEINE LIQUID X 5LTRS", "unit": ""},
    {"code": "15INCON005", "description": "INCONTINENCE BED PADS 40cm x 60cm", "unit": "Number"},
    {"code": "15TOWEL005", "description": "INTERFOLD HAND TOWELS", "unit": "SHEETS"},
    {"code": "01JUGSE010", "description": "JUGS ELECTRIC", "unit": "NUMBER"},
    {"code": "01KNIVE030", "description": "KNIVES TABLE", "unit": "Number"},
    {"code": "03MOPS010", "description": "KENTUCKY MOPS COTTON 400gr", "unit": "Number"},
    {"code": "01MATCH005", "description": "MATCHES", "unit": "Number"},
    {"code": "03MOPS020", "description": "MOP FLAT 60cm", "unit": ""},
    {"code": "03MOPS015", "description": "MOP FLAT 40cm", "unit": ""},
    {"code": "15NAPPI010", "description": "NAPPIES DISPOSABLE ADULT LARGE", "unit": "Number"},
    {"code": "15NAPPI015", "description": "NAPPIES PAEDIATRIC 12 - 25 KILOS", "unit": "NUMBER"},
    {"code": "15NAPPI020", "description": "NAPPIES PAEDIATRIC 2 - 5 KILOS", "unit": "NUMBER"},
    {"code": "10CTIES010", "description": "NYLON CABLE TIES (F/TRANSPARENT & YELLOW REFUSE BAGS ONLY)", "unit": "Number"},
    {"code": "CC-SHOE--001", "description": "OVERSHOES (ITU & THEATERS)", "unit": ""},
    {"code": "03PADS 005", "description": "PADS SCOURING", "unit": ""},
    {"code": "06PADLO005", "description": "PADLOCK BRASS 1\"", "unit": ""},
    {"code": "06PADLO010", "description": "PADLOCK BRASS 1.1/2\"", "unit": ""},
    {"code": "01PANS005", "description": "PANS DUST PLASTIC", "unit": ""},
    {"code": "12FOAM-010", "description": "PILLOWS SOFT SILICONISED FIBRE 50 X 70CM", "unit": "Number"},
    {"code": "03DETER070", "description": "PINE DISINFECTANT X 5 LITRES", "unit": "LTRS."},
    {"code": "01PLATE030", "description": "PLATES DISPOSABLE", "unit": "NUMBER"},
    {"code": "03POWDE010", "description": "POWDER DETERGENT FOR AUTOMATIC WASHING MACHINE", "unit": ""},
    {"code": "03POWDE020", "description": "POWDER SCOURING VIM", "unit": "Number"},
    {"code": "15SHEET005", "description": "SHEET COUCH ROLLS", "unit": "Roll"},
    {"code": "03SHAMP005", "description": "SHAMPOO ADULT", "unit": ""},
    {"code": "03SHAMP010", "description": "SHAMPOO BABY", "unit": ""},
    {"code": "03SKINS005", "description": "SKINS CHAMOIS LEATHER", "unit": "Number"},
    {"code": "03SOAP015", "description": "SOAP FOR BABY", "unit": ""},
    {"code": "03SOAP010", "description": "SOAP TOILET", "unit": "Number"},
    {"code": "03SOAP005", "description": "SOAP LAUNDRY", "unit": "Number"},
    {"code": "03SPONG010", "description": "SPONGES WIRE", "unit": ""},
    {"code": "03SPONG015", "description": "SPONGES BATH", "unit": "Number"},
    {"code": "03SPONG005", "description": "SPONGES SCOURING", "unit": "Number"},
    {"code": "08SPRAY005", "description": "SPRAY AIRFRESHENER 300ML", "unit": "TINS"},
    {"code": "08SPRAY010", "description": "SPRAY INSECTICIDE", "unit": "TINS"},
    {"code": "03SQUEE005", "description": "SQUEEGEES FLOOR 13\"LONG", "unit": "Number"},
    {"code": "03SQUEE010", "description": "SQUEEGEES FLOOR 22\"LONG", "unit": "Number"},
    {"code": "01STRAWS005", "description": "STRAWS DRINGING", "unit": ""},
    {"code": "03STEEL005", "description": "STEEL WOOL SMALL", "unit": "PACK OF 10"},
    {"code": "03STICK005", "description": "STICKS FOR BROOMS/MOPS", "unit": "Number"},
    {"code": "01STRET005", "description": "STRETCH AND SEAL", "unit": "PACKS"},
    {"code": "03SWABS005", "description": "SWABS FLOOR", "unit": "Number"},
    {"code": "15TAPE015", "description": "TAPE COTTON 1/2\"", "unit": ""},
    {"code": "03DETER005", "description": "THICK CLEANING BLEACH X 5 LITRES", "unit": "LTRS."},
    {"code": "01THERMOS", "description": "THERMOS FLASKS", "unit": "Number"},
    {"code": "03CLEAN015", "description": "TOILET CLEANER LIQUID ACID X 500ML", "unit": "BOTTLES"},
    {"code": "01TORCH005", "description": "TORCHES HAND 2 CELL TYPE", "unit": ""},
    {"code": "CC-TWINE-001", "description": "TWINE", "unit": "ROLL"},
    {"code": "15HOLDU005", "description": "UNIVERSAL ATTACHMENT FOR URINE & SECRE.", "unit": ""},
    {"code": "15APRON015", "description": "WHITE DISPOSABLE APRONS FOR DISPENSERS", "unit": "Number"},
    {"code": "01WRING005", "description": "WRINGERS PLASTIC 4100P", "unit": "Number"},
    {"code": "15APRON020", "description": "YELLOW DISPOSABLE APRONS FOR DISPENSERS", "unit": "Number"},
]


ORDER_FORM_DEFS = {
    "mmml-topup": {
        "slug": "mmml-topup",
        "template": "clinic/order_form.html",
        "form_type": "MMML Top-Up (Disposables)",
        "ref_prefix": "MMML-TOPUP",
        "title": "M.M.M.U. IRO Top-Up System List",
        "doc_title": "M.M.M.U. - IRO TOP-UP SYSTEM LIST, DISPOSABLES",
        "subtitle": "Stoma Care Clinic top-up stock list. Complete the "
                    "quantities, then send it to Disposables \u0026 Supplies.",
        "section_ward": "Stoma Care Clinic",
        "cost_centre": "STO-01",
        "ext_default": "25454431/2",
        "note_label": "Team / Day",
        "note_default": "Tuesday Team 1",
        "location": "OUT PATIENTS LEVEL -1",
        "recipient": DISPOSABLES_EMAIL,
        "office_use": True,
        "items": TOPUP_ITEMS,
        # key, header label, fillable (an input the user completes)
        "columns": [
            {"key": "code", "label": "EQ Number", "fill": False, "w": "15%"},
            {"key": "description", "label": "Item Description", "fill": False, "left": True, "w": "42%"},
            {"key": "topup", "label": "Top Up Quantity", "fill": False, "center": True, "w": "13%"},
            {"key": "required", "label": "Required", "fill": True, "w": "15%"},
            {"key": "supplied", "label": "Supplied", "fill": True, "w": "15%"},
        ],
    },
    "cleaning": {
        "slug": "cleaning",
        "template": "clinic/order_form.html",
        "form_type": "Cleaning Consumables Order",
        "ref_prefix": "CLEAN-STO01",
        "title": "Cleaning Consumables Order List",
        "doc_title": "CLEANING CONSUMABLES ORDER LIST",
        "subtitle": "Stoma Care Clinic cleaning consumables. Complete the "
                    "quota / demand, then send it to Disposables \u0026 Supplies.",
        "section_ward": "Stoma Care Clinic",
        "cost_centre": "STO-01",
        "ext_default": "4431/2",
        "note_label": "Remarks",
        "note_default": "TEAM 1 - TUESDAY",
        "location": "",
        "recipient": DISPOSABLES_EMAIL,
        "office_use": False,
        "items": CLEANING_ITEMS,
        "columns": [
            {"key": "code", "label": "SLH Stock Code", "fill": False, "w": "20%"},
            {"key": "description", "label": "Stock Item Description", "fill": False, "left": True, "w": "38%"},
            {"key": "unit", "label": "Unit", "fill": False, "center": True, "w": "10%"},
            {"key": "quota", "label": "Quota", "fill": True, "w": "10%"},
            {"key": "demand", "label": "Demand", "fill": True, "w": "10%"},
            {"key": "supply", "label": "Supply", "fill": True, "w": "12%"},
        ],
    },
}

# form_type (stored on each OrderingDocument) -> slug, so the archive and the
# document detail page can find a form's layout again after it is saved.
FORM_TYPE_TO_SLUG = {d["form_type"]: s for s, d in ORDER_FORM_DEFS.items()}


def get_form_def(slug):
    """Return the definition for a form slug, or None if unknown."""
    return ORDER_FORM_DEFS.get(slug)


def def_for_form_type(form_type):
    """Return the definition for a stored OrderingDocument.form_type, or None."""
    return ORDER_FORM_DEFS.get(FORM_TYPE_TO_SLUG.get(form_type))
