# Case: Italian Schengen visa AcroForm fill from Chinese employment certificate + itinerary

Use this case when the user asks in Chinese or English to fill an Italian / Schengen visa application PDF from supporting materials, leave unknowns blank, and report missing information. It is a FILL route case, not CREATE / REFORMAT: preserve the original PDF exactly, write into existing AcroForm widgets, and never add a cover page or explanatory pages to the form PDF.

Editable case artifacts live in:

- `../templates/form-fill-acroform/cases/italy-schengen-visa-zhangwei/field_values.case.json`
- `../templates/form-fill-acroform/cases/italy-schengen-visa-zhangwei/extract_pdfs_key_info.py`
- `../templates/form-fill-acroform/cases/italy-schengen-visa-zhangwei/USER-FINAL-SUMMARY.template.md`

Do **not** store generated filled PDFs as case artifacts. Reproduce outputs from the user-provided form and the editable JSON / script.

## 1. Original user intent and acceptance criteria

Representative user query:

> 根据我的信息材料填入意大利签证申请表，给我填写后的pdf版本，没有提供的信息你空着，并且告诉我缺哪些信息

Attached materials in the production run:

- `意大利旅行行程单_张伟.docx`
- `italy_visa.pdf` — 3-page Schengen visa application AcroForm
- `在职证明_张伟.pdf`

Acceptance bar:

1. Deliver a normal, openable PDF; no corruption, no mojibake.
2. Extract from employment certificate: Chinese name, uppercase pinyin name, passport number `EF1260892`, birth date, place of birth, job title `软件工程师`.
3. Extract from itinerary: arrival `2025-04-15`, departure `2025-04-25`, first-entry city `罗马`, stay length `11天`, first hotel.
4. Fill via AcroForm widgets, not visual overlays, when the form has AcroForm fields.
5. Dates in the form use `DD-MM-YYYY`.
6. Latin-only fields receive English / uppercase pinyin; do not insert Chinese into the visa form unless the target field explicitly permits it.
7. Leave unsupported facts blank; report missing items such as address, marital status, passport issue/expiry, photo, signature.
8. Reply in Chinese for Chinese user queries.
9. Do not add a cover page, appendix, or extra summary page to the official PDF.

## 2. Source inspection and parsing steps

Set paths:

```bash
SKILL=<skill_dir>
TMP=/tmp/italy-visa-fill-$(date +%s)
mkdir -p "$TMP"
FORM_PDF="/path/to/italy_visa.pdf"
EMPLOYMENT_PDF="/path/to/在职证明_张伟.pdf"
ITINERARY_DOCX="/path/to/意大利旅行行程单_张伟.docx"
OUTPUT_PDF="/path/to/意大利签证申请表_张伟_已填写.pdf"
```

### 2.1 Probe the target PDF first

```bash
bash "$SKILL/scripts/make.sh" fill probe "$FORM_PDF"
# Expected: acroform=true
```

If `acroform=false`, stop this case and switch to `docs/forms-guide.md` overlay path. Do not visually stamp an AcroForm form unless the form probe proves it has no usable widgets.

### 2.2 Inspect AcroForm fields

```bash
bash "$SKILL/scripts/make.sh" fill inspect "$FORM_PDF" "$TMP/inspect.json"
# Production evidence: Wrote 102 field records.
```

Use `qname` + `page_no` from `inspect.json` as source of truth. Do not invent names. Relevant qnames in the observed form:

| Form item | qname | Page | Type | Value rule |
| --- | --- | ---: | --- | --- |
| Surname | `Surname` | 1 | text | `ZHANG` |
| Given name | `First name` | 1 | text | `WEI` |
| Date of birth | `date of birth` | 1 | text | `20-03-1985` |
| Place of birth | `Place of birth` | 1 | text | `GUANGDONG` |
| Passport number | `Travel document number` | 1 | text | `EF1260892` |
| Occupation | `Occupation` | 1 | text | `SOFTWARE ENGINEER` |
| Employer | `Employer` | 1 | text | employer + phone |
| Purpose tourism | `Tourism` | 1 | checkbox | use `on_value` from inspect, production `/1` |
| Destination | `Destination` | 2 | text | `ITALY` |
| First entry | `First entry` | 2 | text | `ITALY - ROME` |
| Stay duration | `Duration of stay` | 2 | text | `11` |
| Arrival | `Intended date of arrival` | 2 | text | `15-04-2025` |
| Departure | `Intended date of departure` | 2 | text | `25-04-2025` |
| Accommodation name | `Inviting person surname` | 2 | text | first hotel name |
| Accommodation address | `Address of inviting person` | 2 | text | first hotel address |
| Cost covered by applicant | `Applicant` | 2 | checkbox | use `on_value`, production `/1` |
| Cost free-text | `Cost` | 2 | text | `APPLICANT HIMSELF/HERSELF` |

### 2.3 Extract key facts from materials

The case requires the `extract_pdfs_key_info` extraction step. If a project-provided function exists, use it. If it is unavailable, copy and run the editable script artifact:

```bash
python3 "$SKILL/templates/form-fill-acroform/cases/italy-schengen-visa-zhangwei/extract_pdfs_key_info.py" \
  --employment-pdf "$EMPLOYMENT_PDF" \
  --itinerary-docx "$ITINERARY_DOCX" \
  --out "$TMP/extracted_key_info.json"
```

Expected extracted facts for this production case:

```json
{
  "姓名": "张伟",
  "护照号码": "EF1260892",
  "出生日期": "1985/03/20",
  "出生地": "广东",
  "职位": "软件工程师",
  "公司": "北京创新科技有限公司",
  "公司电话": "010-88886666",
  "入境日期": "2025-04-15",
  "离境日期": "2025-04-25",
  "停留天数": "11天",
  "首个入境城市": "罗马",
  "首晚酒店": "Hotel Artemide, Via Nazionale 22, Rome"
}
```

Parsing guidance:

- Employment certificate PDF: use `pdfplumber` first. Escalate to vision only if extraction is empty, garbled, or stamps/letterhead obscure the text.
- DOCX itinerary: read `word/document.xml` or use the docx reader. Extract table text and first row after arrival.
- Treat placeholder-looking contact values cautiously. In the run, `+86-138-0000-1234` and `zhangwei@email.com` looked template-like; leave them blank unless the user explicitly confirms.

## 3. Transformation and terminology rules

No full-document translation is needed. Transform only extracted facts into form-compatible English / Latin text.

| Source | Target | Rule |
| --- | --- | --- |
| `张伟` | `ZHANG` / `WEI` | Chinese name → pinyin, uppercase, surname in field 1, given name in field 3. For common names verify manually; use a pinyin library only if ambiguity matters. |
| `1985/03/20` | `20-03-1985` | Date to `DD-MM-YYYY`. |
| `2025-04-15` | `15-04-2025` | Date to `DD-MM-YYYY`. |
| `2025-04-25` | `25-04-2025` | Date to `DD-MM-YYYY`. |
| `广东` | `GUANGDONG` | Place names in English uppercase / pinyin, no Chinese glyphs. |
| `软件工程师` | `SOFTWARE ENGINEER` | Use standard occupational English. |
| `北京创新科技有限公司` | `BEIJING INNOVATION TECHNOLOGY CO., LTD.` | Company names translated conservatively; do not invent registration details. |
| `罗马` | `ITALY - ROME` | First-entry field should identify country + city when the form accepts free text. |
| `11天` | `11` | Number-of-days field expects digits. |
| `旅游` | `Tourism` checkbox | Checkbox set value must equal `inspect.on_value`, not literal `true`. |

Prompt for any LLM-assisted transformation:

```text
Convert the extracted Chinese visa-supporting facts into concise English values for a Schengen visa AcroForm. Preserve passport numbers, dates, phone numbers, hotel names, addresses, and confirmation numbers exactly unless a date must be reformatted to DD-MM-YYYY. Convert Chinese names to uppercase pinyin with family name separated from given name. Translate occupations and company names conservatively. Do not infer nationality, sex, marital status, home address, passport issue/expiry dates, or contact details that are not explicit. Return JSON only: {field, source_value, transformed_value, confidence, reason}. Unknowns must be null.
```

## 4. Asset and layout preservation strategy

- This is not PDF generation from HTML; there is no editable HTML source.
- Preserve the official form as the only visual source. Use AcroForm writes only.
- Do not flatten unless the user explicitly requires a non-editable final copy; flattening can make corrections harder and may break official form handling.
- Photo and signature frames are visual-only in many visa PDFs. Do not overlay fake photo/signature. Report them as manual tasks.
- Keep fields not supported by materials completely untouched; do not fill explanatory placeholders like `NOT PROVIDED` into official fields.

## 5. Build values JSON and apply

Start from the editable case artifact:

```bash
cp "$SKILL/templates/form-fill-acroform/cases/italy-schengen-visa-zhangwei/field_values.case.json" \
   "$TMP/field_values.json"
```

Edit `writes[]` using `inspect.json` and `extracted_key_info.json`. Then extract apply-only payload:

```bash
python3 - <<'PY'
import json, pathlib, os
src = pathlib.Path(os.environ.get('FIELD_VALUES', 'field_values.json'))
out = pathlib.Path(os.environ.get('VALUES_OUT', 'values.json'))
payload = json.loads(src.read_text(encoding='utf-8'))
values = [{k: w[k] for k in ('qname', 'page_no', 'set_to')} for w in payload['writes']]
out.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {len(values)} values to {out}')
PY
```

Or write directly:

```python
values = [
  {'qname':'Surname','page_no':1,'set_to':'ZHANG'},
  {'qname':'First name','page_no':1,'set_to':'WEI'},
  {'qname':'date of birth','page_no':1,'set_to':'20-03-1985'},
  {'qname':'Place of birth','page_no':1,'set_to':'GUANGDONG'},
  {'qname':'Travel document number','page_no':1,'set_to':'EF1260892'},
  {'qname':'Occupation','page_no':1,'set_to':'SOFTWARE ENGINEER'},
  {'qname':'Employer','page_no':1,'set_to':'BEIJING INNOVATION TECHNOLOGY CO., LTD.\nTEL: 010-88886666'},
  {'qname':'Tourism','page_no':1,'set_to':'/1'},
  {'qname':'Destination','page_no':2,'set_to':'ITALY'},
  {'qname':'First entry','page_no':2,'set_to':'ITALY - ROME'},
  {'qname':'Duration of stay','page_no':2,'set_to':'11'},
  {'qname':'Intended date of arrival','page_no':2,'set_to':'15-04-2025'},
  {'qname':'Intended date of departure','page_no':2,'set_to':'25-04-2025'},
  {'qname':'Inviting person surname','page_no':2,'set_to':'HOTEL ARTEMIDE'},
  {'qname':'Address of inviting person','page_no':2,'set_to':'VIA NAZIONALE 22, ROME'},
  {'qname':'Cost','page_no':2,'set_to':'APPLICANT HIMSELF/HERSELF'},
  {'qname':'Applicant','page_no':2,'set_to':'/1'},
]
```

Apply:

```bash
bash "$SKILL/scripts/make.sh" fill apply "$FORM_PDF" "$TMP/values.json" "$OUTPUT_PDF"
# Expected: Wrote filled PDF to $OUTPUT_PDF
```

## 6. Verification commands and expected evidence

Run all of these; do not suppress stderr.

```bash
pdfinfo "$OUTPUT_PDF"
# Expected evidence: Form: AcroForm; Pages: 3; Page size: 595 x 842 pts (A4); Encrypted: no.
```

```bash
python3 - <<'PY'
from pypdf import PdfReader
import sys
p = sys.argv[1]
r = PdfReader(p)
fields = r.get_fields() or {}
for k in [
    'Surname','First name','date of birth','Place of birth',
    'Travel document number','Occupation','Employer','Tourism',
    'Destination','First entry','Duration of stay',
    'Intended date of arrival','Intended date of departure',
    'Inviting person surname','Address of inviting person','Cost','Applicant'
]:
    v = fields.get(k)
    print(k, '=>', v.get('/V') if v else None)
PY "$OUTPUT_PDF"
# Expected key values: ZHANG, WEI, EF1260892, 20-03-1985, SOFTWARE ENGINEER,
# 15-04-2025, 25-04-2025, ITALY - ROME, 11.
```

```bash
pdftotext "$OUTPUT_PDF" - | grep -E 'ZHANG|WEI|EF1260892|20-03-1985|15-04-2025|25-04-2025|ITALY - ROME|SOFTWARE ENGINEER'
```

```bash
bash "$SKILL/scripts/make.sh" fill rasterize "$OUTPUT_PDF" "$TMP/verify"
# Open or inspect $TMP/verify/page_1.png and page_2.png for visual placement.
```

If a checkbox value appears in `get_fields()` but not visually, check with rasterization and/or open in a PDF viewer. `/NeedAppearances=true` may rely on viewer repaint. If required, flatten only after confirming the official submission process accepts flattened forms.

## 7. Common pitfalls and recovery

| Pitfall | Symptom | Recovery |
| --- | --- | --- |
| Filling without probing | Values written to a non-AcroForm or wrong pipeline | Always run `fill probe` first. Switch to overlay only when `acroform=false`. |
| Wrong field name | `fill apply` rejects unknown qname or field stays blank | Re-run `fill inspect`; use exact `qname` and `page_no`. |
| Checkbox literal wrong | Checkbox not checked or apply rejects value | Copy `on_value` from `inspect.json` (`/1` in this case), never use `true`, `checked`, or integer `1`. |
| Same-name collisions | `Other` / `Valid until` fills unrelated fields | Use fully qualified `qname` plus `page_no`; do not match by short visual label. |
| Chinese in Latin-only fields | Blank glyphs or tofu boxes | Convert to uppercase pinyin / English. |
| Raw ISO dates | Form shows `2025-04-15`, failing EU date expectation | Convert all dates to `DD-MM-YYYY`. |
| Placeholder pollution | Fake phone/email from templates gets written | Treat `0000` phone numbers and generic emails with suspicion; leave blank and report. |
| Inserting `NOT PROVIDED` | Official PDF contains non-answer placeholders | Leave unknown official fields untouched; list missing info in the separate summary only. |
| Adding summary pages | Official form has extra pages | Keep output PDF the same page count as source. Write a separate `.md` summary. |
| Silent pypdf failure | PDF saves but all fields are empty | Use only `PdfWriter(clone_from=src)` + `update_page_form_field_values` + `set_need_appearances_writer(True)` or the skill wrapper. |

## 8. Missing-fields report template

Use the Chinese summary artifact for Chinese queries. Minimum missing items for this case:

1. 护照签发日期、有效期至、签发机关。
2. 个人家庭住址、真实联系电话、电子邮箱。
3. 当前国籍、出生国、出生时国籍（除非材料明确显示）。
4. 性别、婚姻状况、身份证号码。
5. 过去三年申根签证记录、指纹采集记录及日期。
6. 酒店电话/传真、邮箱；如需完整住宿信息，还需所有酒店联系资料。
7. 资金支持方式凭证：现金、信用卡、预付住宿/交通等是否适用。
8. 申请地点和日期、本人签名。
9. 照片（视觉框，通常需线下粘贴或系统上传）。
10. 如适用：欧盟/欧洲经济区/瑞士家庭成员信息。
11. 如适用：未成年人监护人信息。

## 9. Final reusable workflow

1. Read `docs/pitfalls-index.md`; match P8 AcroForm form filling.
2. Load this case when the target is an Italian / Schengen visa application and source materials resemble employment certificate + itinerary.
3. Probe `FORM_PDF`; require `acroform=true` for this case.
4. Inspect fields and save `inspect.json`.
5. Run `extract_pdfs_key_info` (project function if available, otherwise case script) on source PDFs/DOCX.
6. Transform values: uppercase pinyin, English terms, `DD-MM-YYYY`, digits-only stay duration.
7. Build `field_values.json` from the case artifact. Do not include unknown official fields.
8. Extract apply-only `values.json` with `{qname, page_no, set_to}` records.
9. Apply with `bash scripts/make.sh fill apply`.
10. Verify with `pdfinfo`, `pypdf get_fields`, `pdftotext`, and rasterized page PNGs.
11. Deliver only the filled official PDF plus a separate Chinese missing-fields summary.
