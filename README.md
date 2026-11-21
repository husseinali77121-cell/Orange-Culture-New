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
| **المقاومة الجوهرية** | 63 صف، مصدر واحد للحقيقة في `clinical_data.py` |
| **قراءة النتيجة** | CLSI M100 Ed36: الـ I حسب الصنف والموقع · الإدخال S / I / R بس؛ الـ SDD اللي المعمل كاتبه بيتقري ويظهر ملاحظة تحت المضاد مع نظام جرعته (v7.7) |
| **استنتاج الآلية** | ESBL · AmpC · carbapenemase · DTR · MRSA · VRE |
| **التصنيف** | MDR/XDR/PDR بجداول Magiorakos منفصلة لكل مجموعة كائنات |
| **بوابات الأمان** | حمل · أطفال · حديثو ولادة (بالشهور) · كلوي · كبدي (Child-Pugh) |
| **QC اللوحة** | تناقضات · تسلسل · فئات مكافئة · أنماط ظاهرية استثنائية · قابلية التبليغ |
| **التتبّع** | 72 قاعدة مربوطة بمصادر مؤرَّخة في `guideline_registry.py` (54 موقَّعة من الطبيب + 17 معتمدة بقرار/تعليمات مالك المعمل بعد مراجعة المصدر — ليست توقيع طبيب، وكلها في طابور توقيع د. طارق)؛ كل قاعدة أصلها EUCAST ليها قرار مراجعة في `eucast_audit.py` |
| **أنواع الكاربابينيميز** | KPC · OXA-48 · MBL — تحدد العامل الحديث المناسب (IDSA AMR 2026) |

## المصادر

**CLSI M100 Ed36 (المرجع الأول لقراءة النتيجة — قرار v6.9)** · CLSI M39 ·
IDSA AMR Guidance 2026 (doi:10.1093/cid/ciag481) · IDSA cUTI 2025 · AAP 2016 (Fluoroquinolones) ·
FDA STIC (Sulopenem · Gepotidacin · Cefepime-enmetazobactam · Fosfomycin IV) ·
EUCAST Intrinsic Resistance v3.3 / Expected Resistant Phenotypes · EUCAST Expert Rules v3.1 ·
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
python -m pytest tests                  # كل شيء (662 اختبار، حوالي 3 دقايق)
python tools/run_test_groups.py         # نفس الاختبارات في 9 مجموعات + JUnit XML لكل مجموعة
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
| `tests/test_v7_9_review.py` | v7.9: حالة Klebsiella / قسطرة فوق العانة: MDR واحد في كل التقارير (XDR غير مؤكد) · Cefepime I غير مؤكد · الكاربابينيم = اختبار مش تشخيص · AD مؤكدة / مشتبهة / محفز تاني · مكان سحب عينة القسطرة · تاجات الصورة · Fosfomycin · Klebsiella للجنس بس |
| `tests/test_v7_8_review.py` | v7.8: تعارض المدخلات (المستحيل والغير منطقي) · V16 القواعد نفسها · V17 القوائم النهائية · mutation testing · العدّادات · ACL على Windows · مجموعات الاختبارات |
| `tests/test_v7_8_ocr.py` | v7.8: قراءة جداول الحساسية من الصور بالمواقع — صفر S غلط (محتاج Tesseract) |
| `tests/test_v7_7_review.py` | v7.7: القوائم S / I / R بس · SDD المعمل ملاحظة تحت المضاد · SDD غلط بيوقف التقارير (V14) · I مش بيتحوّل SDD (PL3) · Daptomycin محتاج E. faecium |
| `tests/test_v7_6_review.py` | v7.6: قرار إصدار واحد قبل أي زرار · V11/V12/V13 · طريقة جمع مش قابلة للتأكيد · تاريخ مصر بالقاعدة · Amox-Clav في الـ OCR · SDD للأزواج اللي CLSI بيعرّفها · فحص عشوائي للمحرك والصفحة |
| `tests/test_v7_5_review.py` | v7.5: الـ Validator بيوقف التصدير · طريقة جمع مش متحددة · gate متخطّى = degraded · تاريخ القاهرة · سجل التوقيعات |
| `tests/test_v7_4_review.py` | v7.4: تعارض تقرير المعمل والحالة · ESBL مشتبه/مؤكد · MDR · أعراض النخاع · أرقام اللوحة · Validation Engine على حالات كاملة |

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
      panel.py allergy.py organism.py new_agents.py mechanism.py age.py specific.py pregnancy.py host.py
    clsi_categories.py      معنى I و SDD حسب CLSI M100 Ed36 (الصنف · الموقع · نظام جرعة الـ SDD)
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
  validation/               case_validator: فحص الحالة كاملة (الشاشة = التقرير = الـ PDF) — v7.4
  common/                   clinical_utils (Patient) · renal · specimen · aux_tests · catalog · util ·
                            data_consistency (تقرير المعمل مقابل الحالة) · drug_names (أسماء/أملاح الأدوية)
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

_الأرقام أعلاه محدَّثة بتاريخ 2026-11-21 (v7.9) مقابل الكود نفسه: **67 دواء · 47 كائن قابل للاختيار (منها 12 غير محدد النوع) · 63 صف مقاومة جوهرية · 72 قاعدة (54 موقَّعة من د. طارق + 18 اتراجعت واتعمدت بقرار المالك في v7.6 وتنتظر توقيعه — منهم 14 متراجعين من مصادر ثانوية، 3 من المصدر الأصلي، و QC003 heuristic) · 2,134 حالة في الـ snapshot**. `test_clinical_facts.py` بيفشل لو أي رقم منهم اتغيّر من غير تحديث. تفاصيل v7.4 (مراجعة v7.3 + مراجعة حالة E. coli / إصابة النخاع: تعارض طريقة الجمع بين تقرير المعمل والبرنامج بيوقف التقارير، «Suspected ESBL» بدل ESBL+، فئات MDR كاملة، أعراض النخاع «جديدة ولا من قبل»، أرقام لوحة الحساسية بتتطابق، Validation Engine للحالة كاملة) في §16؛ تفاصيل v7.9 (مراجعة حالة Klebsiella / قسطرة فوق العانة: MDR/XDR موحّد، صياغة الكاربابينيميز والكينولون، تأكيد الـ autonomic dysreflexia، مكان سحب عينة القسطرة، Fosfomycin، Klebsiella للجنس بس) في §21؛ تفاصيل v7.8 (حماية من تعارض المدخلات والقواعد V16/V17، قراءة جداول الـ OCR بالمواقع ومراجعة إجبارية V15، ACL على Windows، مجموعات الاختبارات) في §20؛ تفاصيل v7.7 (الـ SDD خرج من الاختيارات وبقى ملاحظة تحت المضاد، V14، رسالة PL3، Daptomycin و VRE) في §19؛ تفاصيل v7.6 (قرار إصدار واحد قبل أي زرار، V11/V12/V13 أدق، فحص منهجي لقى قراءة Amox-Clav غلط وتقارير غير البول اللي كانت هتتوقف، SDD للأزواج اللي CLSI بيعرّفها، اعتماد المالك للقواعد المعلّقة) في §18؛ تفاصيل v7.5 (أي خطأ من الـ Validator بيوقف التصدير كله، تنبيه لما طريقة الجمع مش متحددة، تخطّي الـ gate بيتسجّل كـ degraded، تاريخ القاهرة في اختبار المراجع، تنظيف سجل التوقيعات) في §17؛ تفاصيل v7.3 (المراجعة الخارجية التالتة: مكان الـ UTI منفصل عن التعقيد، BAL/PSB محتاجين عدّ فعلي، SIRS، موافقة الطبيب مربوطة بالتقييم، درجة خطورة قواعد اللوحة = كلام السجل، mecC، حد الـ 60 يوم) في §15؛ تفاصيل v7.2 (التحقق من المراجعة الخارجية التانية: حكم «لا علاج» بيوقف التوصيات، cUTI مش حويضة، مزارع الدم بالمجموعات، عتبات AAP، العينات التنفسية، خطورة تعارضات اللوحة) في §14؛ تفاصيل v7.1 (مراجعة تانية لكل القواعد والـ Pathogenicity + المراجعة الخارجية لـ v7.0: IDSA cUTI 2025، ACOG 2023، عتبات NIDRR، DTR، الكاربابينيميز المؤكد) في §13 ومكان EUCAST في `DECISIONS_2026-11-14.md`؛ v7.0 (مراجعة حالة الـ CA-UTI، مراجعة قواعد EUCAST، phenotype-plausibility، تقارير صفحة واحدة) في `CHANGELOG_2026-11-12.md` §12 و `EUCAST_AUDIT_2026-11-19.md`؛ v6.9 في §11 و `DECISIONS_2026-11-14.md`._
