# Orange Culture Analyzer

> **رفع النسخة في repo جديد:** الخطوات في [`NEW_REPO_SETUP.md`](NEW_REPO_SETUP.md).

نظام دعم قرار سريري (CDSS) لتفسير مزارع الميكروبيولوجي واختبارات الحساسية،
مبني على Streamlit. يقرأ لوحة الحساسية، يستنتج آلية المقاومة، يصنّف
MDR/XDR/PDR، ويُخرج قائمة أدوية مفلترة حسب الكائن والعيّنة وحالة المريض.

> **تنبيه:** أداة مساعدة للقرار. لا تُغني عن حكم أخصائي الميكروبيولوجي أو
> الطبيب المعالج، ولا تُستخدم كمصدر وحيد لقرار علاجي.

## القدرات

| | |
|---|---|
| **المقاومة الجوهرية** | 57 صف، مصدر واحد للحقيقة في `clinical_data.py` |
| **استنتاج الآلية** | ESBL · AmpC · carbapenemase · DTR · MRSA · VRE |
| **التصنيف** | MDR/XDR/PDR بجداول Magiorakos منفصلة لكل مجموعة كائنات |
| **بوابات الأمان** | حمل · أطفال · حديثو ولادة (بالشهور) · كلوي · كبدي (Child-Pugh) |
| **QC اللوحة** | تناقضات · تسلسل · فئات مكافئة · أنماط ظاهرية استثنائية · قابلية التبليغ |
| **التتبّع** | 67 قاعدة مربوطة بمصادر مؤرَّخة في `guideline_registry.py` (60 موقَّعة من الطبيب + 7 أُضيفت في مراجعة 2026-11-10 واعتُمدت بتعليمات مالك المعمل بعد مراجعة المصدر — ليست توقيع طبيب) |
| **أنواع الكاربابينيميز** | KPC · OXA-48 · MBL — تحدد العامل الحديث المناسب (IDSA AMR 2026) |

## المصادر

EUCAST Breakpoint Tables v16.1 · EUCAST Intrinsic Resistance v3.3 ·
EUCAST Expert Rules v3.1 · CLSI M100 Ed36 · CLSI M39 ·
IDSA AMR Guidance 2026 (doi:10.1093/cid/ciag481) · IDSA cUTI 2025 ·
ATS/IDSA HAP/VAP 2016 · BALANCE (NEJM 2025) · ACOG CO 717/797 · AAP Red Book 2024 ·
WHO AWaRe 2025 ·
Magiorakos et al., *Clin Microbiol Infect* 2012;18:268-281

## التشغيل

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## الإعداد — `.streamlit/secrets.toml`

```toml
# هوية البائع (تظهر في صفحة الدخول ورسائل التجديد)
vendor_name  = "Orange Lab"
vendor_phone = "+20 ..."
vendor_email = "support@example.com"

# المشتركون: البريد -> تاريخ الانتهاء
subscribers = '{"lab@example.com": "2026-12-31"}'

# كلمات المرور (اختياري لكن موصى به بشدة)
# من غيرها الدخول بالبريد وحده، والتطبيق هيعرض تحذير عند البدء
subscriber_hashes = '{"lab@example.com": "pbkdf2_sha256$240000$...$..."}'
```

توليد الـ hash:

```bash
python -c "from cdss.security.passwords import make_password_hash; print(make_password_hash('كلمة-السر'))"
```

## الاختبارات

```bash
pip install -r requirements-dev.txt     # pytest فقط — الاختبارات لا تحتاج streamlit ولا tesseract
python -m pytest tests                  # كل شيء (حوالي 4 دقائق)
python -m pytest tests --deselect tests/test_legacy_suites.py    # الجديد فقط (ثوانٍ)
```

| الملف | يثبت ماذا |
|---|---|
| `tests/test_architecture.py` | المحرك لا يستورد streamlit · جدول القواعد وترتيبه · ميزانية حجم الملفات |
| `tests/test_outcome_and_engine.py` | **التحذير لا يُخفي منعاً لاحقاً** — الضمان الأساسي للمحرك |
| `tests/test_rules_unit.py` | كل rule لوحدها: سياق واحد، دواء واحد، نتيجة واحدة |
| `tests/test_aux_tests.py` | D-test و Penicillinase يصلان للقواعد |
| `tests/test_properties.py` | خصائص على حالات عشوائية: كل دواء في خانة واحدة · R لا يُقترح أبداً · الترتيب لا يؤثر · عامل الخطورة لا يُرخي حكماً |
| `tests/test_ui_page.py` | الصفحة كاملة تحت Streamlit وهمي (بدون متصفح) |
| `tests/test_packaging.py` | ملف الـ EXE يحمل كل module تلقائياً |
| `tests/test_legacy_suites.py` | الـ 21 suite القديمة (`tests/legacy/`) كما هي |

`tests/legacy/test_scenarios.py` بيقارن بـ golden snapshot. أي تغيّر في إجابة سريرية
بيكسر البناء عن قصد — راجع الـ diff، وبعدين:

```bash
python tests/legacy/test_scenarios.py --update
```

## البنية

التفاصيل في [`ARCHITECTURE.md`](ARCHITECTURE.md).

```
streamlit_app.py            نقطة الدخول (سطران): from cdss_ui.app import main; main()

cdss/                       المحرك السريري — لا يستورد streamlit إطلاقاً
  pipeline.py               run_analysis(): المسار كله في دالة واحدة نقية
  therapy/
    engine.py               analyze_antibiotics(): جدول RULES بالترتيب + الحلقة
    context.py              TherapyContext: الحالة مرة واحدة، مجمَّدة (frozen)
    outcome.py              Outcome: المنع نهائي، التحذير لا يوقف المسار
    rules/                  القواعد العلاجية، كل واحدة دالة صغيرة:
      panel.py allergy.py organism.py mechanism.py age.py specific.py pregnancy.py host.py
    postprocess.py          خطوات اللوحة كلها: upper UTI، الملاحظات، الترتيب، فلتر العيّنة
    safety_gate.py          بوابة الأمان النهائية (طبقة مستقلة)
    clinical_matrix.py      خريطة القيود التي تقرأها البوابة
    therapy_rules.py tables.py intrinsic.py notes.py drug_classes.py panel_filters.py
  resistance/               mdr.py · mechanism.py (ESBL/AmpC/carbapenemase) · phenotypes.py
  stewardship/              duration · severity · iv_po · combination · deescalation · ranking · syndrome · hepatic
  astqc/                    ast_qa_engine · ast_reportability · ast_consistency · ast_panel_completeness · inline_qc · confidence · final_checklist
  formulary/                abx_guidelines (الدستور الدوائي) · commercial_names(.txt) · co_medications
  organisms/                clinical_data (المقاومة الجوهرية — مصدر الحقيقة الوحيد) · organism_profile · specimen_organism_map · pathogenicity
  ocr/                      image · ocr_parsing · detect · extract
  reports/                  report_service (نص/PDF/صورة) · qa_pdf · patho_pdf · html_utils
  guidelines/               guideline_registry: ربط كل قاعدة بمصدرها المؤرَّخ
  common/                   clinical_utils (Patient) · renal · specimen · aux_tests · catalog · util
  security/                 auth_service · passwords

cdss_ui/                    صفحة Streamlit — لا قرار سريري هنا
  app.py                    main(): فهرس الصفحة، ينادي الأقسام بالترتيب
  inputs.py panel_editor.py analysis.py recommendations.py resistance_panels.py
  stewardship_panels.py report_panels.py pathogenicity_panel.py page_setup.py
  report_intake.py auth.py state.py startup.py patho_view.py

tests/                      pytest + tests/legacy (الـ suites القديمة) + tests/support (Streamlit الوهمي)
tools/differential/         أداة مقارنة النسخة القديمة بالجديدة (تُشغَّل يدوياً)
```

---

_الأرقام أعلاه محدَّثة بتاريخ 2026-11-10 مقابل الكود نفسه: **62 دواء · 46 كائن قابل للاختيار (منها 12 غير محدد النوع) · 57 صف مقاومة جوهرية · 67 قاعدة (60 موقَّعة + 7 معتمدة بتعليمات المالك) · 2,068 حالة في الـ snapshot**. `test_clinical_facts.py` بيفشل لو أي رقم منهم اتغيّر من غير تحديث. تفاصيل مراجعة 2026-11-10 في `CHANGELOG_2026-11-10.md`._
