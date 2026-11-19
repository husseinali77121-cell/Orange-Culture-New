# البنية — Orange Culture Analyzer

هذا الملف يشرح **كيف بُني البرنامج ولماذا**، وأين تضع أي تعديل قادم.

## 1. ثلاث طبقات، اتجاه واحد

```
streamlit_app.py          سطران: from cdss_ui.app import main; main()
        │
        ▼
cdss_ui/   الصفحة         تجمع المدخلات، تنادي run_analysis()، تعرض النتيجة
        │                 لا تتخذ أي قرار سريري
        ▼
cdss/      المحرك          دوال نقية: نفس المدخل ← نفس المخرج
                          لا يستورد streamlit ولا cdss_ui (اختبار يمنع ذلك)
```

الاستيراد يسير لأسفل فقط. المحرك كله يُستورد ويُختبر في بيئة ليس فيها Streamlit
(`tests/test_architecture.py::test_engine_imports_in_a_process_that_has_no_streamlit`).

## 2. المحرك العلاجي — `cdss/therapy/`

كان القرار العلاجي دالة واحدة من 1,337 سطراً: حلقة على الأدوية، وكل تحذير ينتهي بـ
`continue`. أي فحص مكتوب **بعد** ذلك التحذير في الملف لم يكن يُنفَّذ لهذا الدواء.
ثلاث جولات مراجعة سابقة أصلحت كل واحدة منها حالة من نفس العيب (تحذير الحمل يتخطى
فحص الكبد، تحذير ESBL يتخطى فحص الكلى…). البنية الجديدة تلغي العيب نفسه:

```
build_context(...)  ──►  TherapyContext      الحالة مرة واحدة: الكائن، العيّنة، المريض،
                         (frozen)            الآلية، MRSA، CrCl… لا تستطيع قاعدة تعديلها

لكل دواء في اللوحة:
    Outcome()
    for rule in RULES:                       RULES = الترتيب، في مكان واحد (engine.py)
        rule(cx, dg, out)
        if out.banned: break                 المنع نهائي
                                             التحذير يُسجَّل والدواء يكمل المشي
    الخانة: banned > preg_warn > warned > allowed

خطوات اللوحة كلها (postprocess.py): upper UTI ← الملاحظات ← علامة I ← الترتيب ← فلتر العيّنة
```

### قراءة النتيجة: CLSI M100 Ed36 (v6.9)

اللوحة الخام ممكن تحمل `SDD`. `pipeline.run_analysis()` يعطي كل الخطوات نسخة S/I/R
(`clsi_categories.canonical_panel` — SDD تُقرأ I)، ومحرك العلاج وحده يأخذ اللوحة الخام ليعرف
أي دواء SDD (`TherapyContext.sdd`). معنى الـ I / SDD لكل دواء في موقعه يُكتب في
`clsi_categories.intermediate_note()` ويُعلَّق على الدواء (`intermediate_note` / `_en`،
`culture_sdd`). الأدوية الخمسة الجديدة في IDSA 2026 تُحكَم في `rules/new_agents.py`
(نطاق معايير التفسير، الآلية، الموقع) وتضبط `skip_mech` مثل الـ novel BL/BLI، فلا تطبّق
عليها قواعد «بيتا-لاكتام أمام ESBL» القديمة.

### v7.0 — سجل واحد للحالة، وفحص منطقية النمط

- **`cdss/common/case_context.py`** — سجل واحد لحقائق الحالة (طريقة جمع العينة + عوامل المريض)، بيتبني مرة
  واحدة من مدخلات الـ Pathogenicity ويقراه الـ Patient والـ pipeline وكارت الـ syndrome والمدة والصورة والتقرير
  النصي. أي موديول محتاج «القسطرة» أو «الكتلة العضلية» يقرا من هنا، مش من نص ثابت.
- **`cdss/astqc/phenotype_plausibility.py`** — أنماط مش مستحيلة لكن مفيش آلية واحدة تفسّرها، والاختبارات
  اللي تحسمها (PL1–PL4). بيتقرا من محرك الـ QA ولوحة الـ QC وتقرير الجودة، والـ reflex tests بتترقّى في
  `ast_panel_completeness` لـ «ناقص حرج».
- **`organism.rule_qc_no_breakpoint`** — قاعدة العلاج بتقرا نفس جدول `NO_BREAKPOINT_RULES` بتاع الـ QC، فمستحيل
  الـ QC يقول «لا تُفسَّر» والـ Advisory يقترح نفس الدواء.
- **`cdss/guidelines/eucast_audit.py`** — قرار مكتوب لكل قاعدة أصلها EUCAST؛ `citation_line` بيستشهد بـ CLSI أولاً.
- **`cdss/reports/fit_page.py`** — تقرير الـ Pathogenicity وتقرير الجودة بيتعملوا `build(scale)` ويترندروا بأكبر
  حجم خط يدخل صفحة A4 واحدة.

### v7.1 — نفس السجل بيحدد الـ cUTI والجهاز

- **`CaseContext.cuti_device` / `syndrome_device()`** — القسطرة (أي نوع) أو الـ nephrostomy بتخلي الـ UTI
  complicated في الـ pipeline والشاشة بنفس القاعدة (`resolve_uti_syndrome(..., catheter=)`)؛ وكارت الـ syndrome
  بيقرا جهاز العينة نفسها (قسطرة بولية / جهاز تنفس / قسطرة مركزية).
- **`TherapyContext`** — نوع الكاربابينيميز المؤكد في Enterobacterales بيقلب `is_carbapenemase`، و `weight_kg`
  بيوصل للقواعد (حد الوزن في النشرة).
- **`ranking.guideline_tiers(..., sir_map)`** — مستويات للمثانة بدون آلية مقاومة و MSSA، بنفس آلية مستويات IDSA.
- **Pathogenicity** — البول من غير أعراض = بيانات غير كافية؛ البلغم من غير ارتشاح ما يوصلش «true infection»
  (`LRTI_POSSIBLE`)؛ الـ score اسمه «Evidence score» ومش احتمال.

### v7.2 — حكم الـ Pathogenicity بيوصل للتوصيات

- **`pathogenicity.treatment_gate()` / `gate_suppresses()`** — نقطة واحدة: `run_analysis(..., pathogenicity=,
  treat_override=)` بيرجّع `treatment_gate` ويفضّي `ranked` و `duration`؛ الشاشة والتقرير النصي والـ PDF
  (`pdf_parts.section_treatment_gate`) والصورة بيقروا نفس البوابة. قوائم الأمان (allowed / warned / banned)
  بتفضل زي ما هي عشان الـ override يعرض نفس الحاجة.
- **`cdss_ui.state.current_patho_result()`** — النتيجة اللي اتحسبت لمدخلات غير الحالية بتتعلّم stale (توقيع
  `patho_signature`) وما بتتقريش في أي مكان.
- **`uti_syndrome == "cuti"`** — complicated من غير علامات علوية: `TherapyContext.uti_cuti` +
  `rules.specific.rule_cuti_bladder_agents` (تحذير) بدل منع `postprocess.apply_upper_uti`.
- **`ast_consistency`** — `severity` لكل قاعدة (error / warning)، والـ category `verify` ليها رأس 🟠.

### v7.3 — المكان منفصل عن التعقيد، والثقة من السجل

- **`therapy_rules.classify_uti()` → `UtiClass(site, complicated, value, upper_signs, conflict, confirmed)`** —
  `resolve_uti_syndrome()` بيرجّع `.value` بس؛ الصفحة (`analysis._resolve_uti`) بتعرض التعارض وبتطلب التأكيد،
  والقرار بيوصل للتقرير النصي (`uti_note`) والصورة.
- **`cdss_ui.state.treat_override_key()`** — مفتاح الموافقة = بصمة مدخلات التقييم.
- **`ast_consistency`** — الـ `severity` لكل قاعدة لازم يطابق كلام السجل (`test_v7_3_review`).

### الضمانات (وكل واحد عليه اختبار)

| الضمان | كيف | الاختبار |
|---|---|---|
| التحذير لا يُخفي منعاً لاحقاً | `Outcome.caution()` لا يوقف الحلقة | `test_outcome_and_engine.py` |
| الترتيب يحدد **أي سبب يظهر أولاً** فقط، لا **هل يُفحص** | الحلقة تتوقف عند المنع فقط | `test_every_rule_sees_a_cautioned_drug` |
| لا قاعدة تغيّر الحالة لقاعدة أخرى | `TherapyContext` و `DrugUnderTest` مجمَّدان | `test_context_is_frozen` |
| لا قاعدة مكتوبة ومنسية | كل `rule_*` في `rules/` يجب أن يكون في `RULES` | `test_every_rule_function_is_registered` |
| كل دواء في خانة واحدة بالضبط | بناء الخانات في مكان واحد | `test_properties.py::test_partition` |
| عامل الخطورة لا يُرخي حكماً | — | `test_a_risk_factor_never_relaxes_a_verdict` |
| ترتيب اللوحة لا يغيّر النتيجة | — | `test_panel_order_does_not_matter` |
| لا جدول سريري يتعدَّل أثناء التحليل | — | `test_no_clinical_table_is_mutated` |

### شكل القاعدة

```python
def rule_nitrofurantoin_renal(cx, dg, out):
    """Nitrofurantoin below its renal threshold."""
    if "nitrofurantoin" in dg.low and cx.is_renal:
        if cx.crcl is not None and cx.crcl < dg.info.get("renal_limit", 45):
            out.ban(build_banned_item(dg.name, "renal", "...", "..."))
```

- `cx` — الحالة (للقراءة فقط) · `dg` — الدواء ونتيجته (للقراءة فقط) · `out` — ما تقرره القاعدة.
- `out.ban(item)` منع · `out.caution(item)` تحذير · `out.note(drug, level, text, reason)` ملاحظة
  · `cx.alerts.append(text)` تنبيه جانبي.

### إضافة قاعدة جديدة — أربع خطوات

1. اكتب `rule_xxx(cx, dg, out)` في الملف المناسب تحت `cdss/therapy/rules/` مع docstring يذكر المصدر.
2. أضفها إلى `RULES` في `cdss/therapy/engine.py` في مكانها (المنع المطلق قبل تحذيرات المريض؛
   `host.py` دائماً في الآخر).
3. اكتب اختبارها في `tests/test_rules_unit.py` (سياق واحد، دواء واحد — انظر الأمثلة هناك).
4. `python -m pytest tests`. لو تغيّرت إجابة في الـ snapshot راجع الـ diff ثم
   `python tests/legacy/test_scenarios.py --update`.

لو القاعدة تحتاج معلومة جديدة عن الحالة: أضف الحقل في `TherapyContext` واحسبه في
`build_context()` — مرة واحدة، لا داخل القاعدة.

## 3. بوابة الأمان — طبقة ثانية مستقلة

`cdss/therapy/safety_gate.py` + `clinical_matrix.py` تعيد فحص الخانات النهائية مقابل جدول
قيود **منفصل** عن جداول المحرك. التكرار مقصود (defense in depth)، و
`tests/legacy/test_engine_agreement.py` يثبت اتفاق الطبقتين. لا تدمجهما.

المقارنة مع النسخة القديمة أظهرت حالات كان المحرك القديم يمرّرها كتحذير والبوابة هي
التي تمسكها (Ceftriaxone لحديث الولادة مثلاً). المحرك الآن يمنعها بنفسه وبسببها المحدد،
والبوابة تبقى شبكة أمان لا خط الدفاع الأول.

## 4. الصفحة — `cdss_ui/`

`main()` في `app.py` فهرس: ينادي الأقسام (23 دالة) بالترتيب. كل قسم دالة `render_x(page)`.
`page` كائن واحد يحمل ما تتشاركه الأقسام في هذا الـ run (العمر، الكائن، `sir_map`،
الخانات…). المتغير الذي يستخدمه قسم واحد يبقى محلياً فيه.

- لا تضف منطقاً سريرياً في الصفحة. الحساب في `cdss/`، والصفحة تعرض.
- لا تنادِ `analyze_antibiotics` من الصفحة — المسار الوحيد هو `run_analysis()`
  (`test_page_never_calls_the_per_drug_engine_directly`).
- أي widget خاص بالمريض: إما مفتاحه يحمل `file_hash`، أو اسمه في
  `_PATIENT_WIDGET_KEYS` (`cdss_ui/state.py`) — وإلا ورث المريض التالي قيمته
  (`test_unkeyed_patient_widgets_are_all_covered_by_the_reset_list`).
- لا كود يلمس Streamlit وقت الاستيراد؛ `st.set_page_config` أول نداء في كل run
  (`test_set_page_config_is_the_first_streamlit_call_of_every_run`).

الصفحة تُختبر كاملة بدون متصفح: `tests/support/fake_streamlit.py` يسجّل كل نداء
Streamlit ويُرجع قيم widgets مكتوبة أو عشوائية ببذرة ثابتة.

## 5. الاختبارات — ماذا يثبت كل مستوى

| المستوى | الملفات | يثبت |
|---|---|---|
| قاعدة واحدة | `test_rules_unit.py`, `test_aux_tests.py` | كل قاعدة صحيحة وحدها |
| آلية المحرك | `test_outcome_and_engine.py` | المنع نهائي، التحذير لا يوقف |
| خصائص عامة | `test_properties.py` | لا استثناء على أي حالة عشوائية (`CDSS_FUZZ_CASES=5000` لتشغيل أوسع) |
| المسار كاملاً | `tests/legacy/test_pipeline.py`, `test_scenarios.py` (snapshot 2,068 حالة) | الإجابة السريرية لم تتغير |
| الحقائق السريرية | `tests/legacy/test_clinical_facts.py`, `test_guidelines.py` | الجداول = المصادر الموقَّعة |
| الصفحة | `test_ui_page.py` | تُرسم بلا أخطاء، المفاتيح، D-test، QA |
| البنية والتغليف | `test_architecture.py`, `test_packaging.py` | الطبقات، حجم الملفات، الـ EXE |

`tools/differential/` هو الأداة التي قارنت النسخة القديمة بالجديدة حالةً بحالة (انظر `README.md` هناك) — تُشغَّل يدوياً، ليست جزءاً من الـ CI.

`tests/legacy/` هي الـ suites المكتوبة قبل التفكيك. كانت تقطّع `streamlit_app.py` بـ `ast`
وتنفّذ القطع داخل dict؛ الآن تأخذ نفس الأسماء من الـ modules الحقيقية عبر
`legacy_support.py`. تأكيداتها لم تتغير.

## 6. ما لم يُفكَّك بعد

**v6.7 (2026-11-14) — اتفكّك:**

| الدالة | كانت | بقت | فين |
|---|---|---|---|
| `generate_pdf_html_report` | ~1,120 سطر | 225 (توزيع فقط) | الأقسام في `cdss/reports/pdf_sections.py` (دالة لكل قسم)، والـ CSS والنصوص الثابتة والأدوات الصغيرة في `pdf_parts.py`، وجداول الترجمة في `i18n_en.py` |
| `assess_pathogenicity` | ~890 سطر | 299 | `_site_urine` / `_site_respiratory` / `_site_blood` / `_site_csf` / `_site_stool` / `_site_wound` + `_score_purity` + `_score_gram_stain` + `_verdict` (نفس الملف) |
| `generate_decision_tree_image` | ~560 سطر | 365 | الألوان والخطوط والصناديق والنص الملفوف في `cdss/reports/image_parts.py` |
| `generate_report` | ~320 سطر | 159 | `_text_allowed` / `_text_warned` / `_text_banned` / `_text_pathogenicity` / `_text_panel_completeness` |

كل الأجسام اتنقلت **حرف بحرف**: كل قسم بياخد بالاسم بالظبط اللي بيقراه (اتحسب من الـ AST، مش
بالعين)، والناتج اتقارن بايت ببايت قبل وبعد على 600 تقرير (PDF عربي وإنجليزي + التقرير النصي +
صورة الـ decision tree) و 40,000 حالة pathogenicity عشوائية — صفر فرق.
`tests/test_report_split.py` + `tests/golden_outputs.json` بيحفظوا الضمان ده لأي تعديل جاي
(تعديل مقصود: `python tests/test_report_split.py --update` ومراجعة الفرق).

**لسه:**

| الدالة | الطول | الملف |
|---|---|---|
| `predict_esbl` | ~310 سطر | `cdss/resistance/mechanism.py` |
| `classify_mdr` | ~215 سطر | `cdss/resistance/mdr.py` |
| `_site_urine` | ~230 سطر | `cdss/organisms/pathogenicity.py` |

`tests/test_architecture.py::LARGE_BY_DESIGN` يسمّي هذه الاستثناءات صراحةً؛ أي ملف
**جديد** يتجاوز 650 سطراً يفشل الاختبار.

`cdss/health.py`: بوابة الأمان و `clinical_matrix` وجدول المقاومة الجوهرية **إجباريين**
(من غير `try/except`). من غيرهم البرنامج ما يشتغلش أصلاً. باقي وحدات الـ QC (`ast_qa_engine`،
`ast_reportability`، `ast_consistency`، `ast_panel_completeness`) لسه اختيارية: غيابها
بيظهر تحذير أصفر بس، والتوصيات نفسها ما بتتأثرش.

**ليه إجباريين (2026-11-13):** Streamlit بيشغّل كل الـ reruns في نفس الـ Python process. أول رفع
للـ repo الجديد كان ناقصه `cdss/therapy/`. البرنامج وقف وده الصح، بس `cdss.health` كان اتحمّل
بالفعل وعلامة `SAFETY_GATE_AVAILABLE = False`، والـ process فضل محتفظ بيه. بعد ما المجلد
اترفع، البرنامج اشتغل **من غير بوابة الأمان** لحد ما اتعمله reboot. الحل اتنين:
- الطبقات الحرجة ما بقاش ليها وضع "شغّال من غيرها" ممكن يعلق فيه.
- `streamlit_app.py` بيمسح كل modules البرنامج من الذاكرة لو حصل `ImportError`، فأول run
  بعد ما الملف الناقص يوصل بيبدأ نضيف.

الاختبار في `tests/test_partial_upload.py` بيعيد السيناريو ده بالظبط.

## 7. قواعد الصيانة

1. المحتوى السريري (الجداول) يتغير بقرار ومصدر موقَّع في `guideline_registry.py` — لا بتعديل عابر.
2. لا `try: import ...; except: fallback` **جديدة** لـ modules المشروع. الغياب = فشل تشغيل، لا تشغيل ناقص. (الموجود من أيام الملف الواحد محمي بالمسح اللي في `streamlit_app.py`.)
3. لا قوائم ملفات مكتوبة باليد (الـ spec والـ CI يكتشفان الملفات بأنفسهما).
4. كل إصلاح معه اختبار يفشل قبله وينجح بعده.
5. قبل أي release: `python -m pytest tests` ثم `python verify_upload.py --write --release "vX.Y التاريخ (ملخص)"` (بيحفظ hashes النسخة اللي فاتت كتاريخ، عشان Guard 0 يعرف النسخة القديمة لو اترفعت بالغلط).
