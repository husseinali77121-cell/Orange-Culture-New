# مراجعة قواعد EUCAST — 2026-11-19 (v7.0)

**السؤال:** «اعمل مراجعة لأي سبب يبقى EUCAST rule لسه موجودة» — بعد قرار D1 (CLSI M100 Ed36 في كل حاجة).

اتراجع **42 صف** في `guideline_registry.py` مصدره الأصلي وثيقة EUCAST. لكل صف قرار من تلاتة، ومسجّل في `cdss/guidelines/eucast_audit.py` — والاختبار `tests/test_v7_0_review.py` بيفشل لو اتضاف صف EUCAST من غير قرار.

| القرار | العدد | المعنى |
|---|---|---|
| **CLSI-concordant** | 32 | CLSI بيقول نفس الكلام ← اتنقل الاستشهاد لـ CLSI أولاً؛ القاعدة نفسها ما اتغيّرتش |
| **EUCAST-only** | 7 | مالهاش مقابل في CLSI ومفيش تعارض ← فضلت (السبب جنبها) |
| **Converted** | 3 | CLSI مختلف ← السلوك اتغيّر لـ CLSI |

## اللي اتغيّر فعلاً (Converted)

| القاعدة | قبل | بعد (CLSI) |
|---|---|---|
| `intr_serratia` | Tetracycline / Doxycycline «مقاومة جوهرية» (EUCAST v3.3 Table 1 fn.5) | بيتبلّغوا زي ما اتختبروا (CLSI Appendix B1 ما بيذكرهمش)، مع **تحذير علاجي** فيه معلومة EUCAST |
| `nobp_cefoperazone` | Cefoperazone و Cefoperazone-sulbactam «بلا breakpoint» لكل الكائنات | **Cefoperazone لوحده + Enterobacterales:** بيتقرا بمعيار CLSI (S ≤ 16 / R ≥ 64) مع تحذير إنه معيار قديم. **Cefoperazone-sulbactam:** بلا breakpoint لأي كائن (ومش خيار علاجي). **Cefoperazone لوحده مع غير الـ Enterobacterales:** بلا breakpoint (صف جديد `nobp_cefoperazone_non_enterobacterales`) |
| `nobp_tigecycline_proteae` | Serratia ضمنهم («نشاط غير كافٍ» — ملاحظة EUCAST) | Serratia خرجت (معايير FDA STIC بتغطيها؛ CLSI مالوش معايير tigecycline أصلاً) — وملاحظة EUCAST بقت تحذير علاجي. الـ Proteeae زي ما هي (نشرة FDA نفسها) |

## اللي فضل EUCAST ومن غير تغيير — وليه

| القاعدة | السبب |
|---|---|
| `intr_haemophilus_gram_pos_agents` | CLSI publishes no Haemophilus criteria for glycopeptides, oxazolidinones, daptomycin, fusidic acid or clindamycin, so there is nothing to convert to. Kept because it blocks a Gram-positive-only agent reported S on a Gram-negative. |
| `equiv_amc_sam` | A laboratory-consistency check (a split result is a reading error). CLSI has no statement either way. Kept: it catches transcription errors. |
| `hier_amp_vs_amc` | Logic, not a breakpoint: adding an inhibitor cannot lower activity. No CLSI counterpart is needed and none contradicts it. |
| `hier_pip_vs_tzp` | Same logic as hier_amp_vs_amc. |
| `hier_mem_vs_etp` | Mechanism logic (ertapenem is the most labile carbapenem). CLSI uses the same fact for carbapenemase screening; no contradiction. |
| `hier_van_vs_tei_enterococcus` | Mechanism logic (VanA / VanB / VanC). No CLSI counterpart; no contradiction. |
| `QC003` | An unusual-phenotype verification prompt (carbapenem-S, colistin-R amid broad resistance). CLSI has no counterpart; asking to confirm the ID harms nothing. |

## الباقي: CLSI بيقول نفس الكلام

القاعدة زي ما هي، والاستشهاد في التقارير وفي لوحة الـ QC بقى **CLSI أولاً** (EUCAST تاني).

| القاعدة | موضعها في CLSI |
|---|---|
| `intr_anaerobes_aminoglycosides_polymyxins` | CLSI M11-Ed9 (aminoglycosides inactive against anaerobes) |
| `intr_entero_gram_pos_agents` | CLSI M100 Ed36 Appendix B1 (header list for all Enterobacterales) |
| `intr_klebsiella_ampicillin` | CLSI M100 Ed36 Appendix B1 |
| `intr_proteus_mirabilis` | CLSI M100 Ed36 Appendix B1 |
| `intr_morganella_providencia_proteus_vulgaris` | CLSI M100 Ed36 Appendix B1 |
| `intr_proteus_vulgaris_penneri` | CLSI M100 Ed36 Appendix B1 |
| `intr_hafnia_colistin` | CLSI M100 Ed36 Appendix B1 |
| `intr_pseudomonas` | CLSI M100 Ed36 Appendix B2 |
| `intr_stenotrophomonas` | CLSI M100 Ed36 Appendix B2 |
| `intr_mrsa_betalactams` | CLSI M100 Ed36 Table 2C |
| `intr_mycoplasma_cellwall_agents` | CLSI M43 |
| `intr_staph_gram_neg_agents` | CLSI M100 Ed36 Appendix B3 |
| `intr_enterococcus_cephalosporins` | CLSI M100 Ed36 Appendix B4 · Table 2D |
| `intr_strep_enterococcus_aminoglycosides` | CLSI M100 Ed36 Table 2D (HLAR screen only) |
| `intr_enterococcus_sxt_invivo` | CLSI M100 Ed36 Table 2D / Appendix B4 |
| `intr_listeria_cephalosporins` | CLSI M45 Ed3 (Listeria) |
| `intr_nonfermenter_narrow_spectrum` | CLSI M100 Ed36 Appendix B2 |
| `intr_citrobacter_koseri_klebsiella_oxytoca_classA` | CLSI M100 Ed36 Appendix B1 |
| `nobp_nonfermenter_narrow_spectrum` | CLSI M100 Ed36 Tables 2B-2 / 2B-3 / 2B-4 (no criteria) |
| `nobp_azithromycin_enterobacterales` | CLSI M100 Ed36 Table 2A (azithromycin: Salmonella Typhi and Shigella only) |
| `nobp_fosfomycin_oral_non_ecoli` | CLSI M100 Ed36 Table 2A (fosfomycin: E. coli urinary isolates only) |
| `rare_linezolid_gram_pos` | CLSI M100 Ed36 Appendix A (linezolid-resistant: confirm ID and AST) |
| `rare_colistin_disc` | CLSI M100 Ed36 Tables 2A / 2B-1 / 2B-2 (colistin: broth microdilution, CBDE or CAT only) |
| `equiv_ctx_cro` | CLSI M100 Ed36 Table 2A (identical criteria) |
| `hier_tet_vs_doxy` | CLSI M100 Ed36 Table 2A (tetracycline-S predicts doxycycline and minocycline-S) |
| `hier_pen_vs_cro_pneumococcus` | CLSI M100 Ed36 Table 2G |
| `hier_pen_vs_ctx_pneumococcus` | CLSI M100 Ed36 Table 2G |
| `QC004` | CLSI M100 Ed36 Tables 3B / 3C (mCIM / eCIM) |
| `QC004b` | CLSI M100 Ed36 Table 2A (imipenem comment: Proteus, Providencia, Morganella) · Tables 3B / 3C |
| `QC006` | CLSI M100 Ed36 Table 3A (current breakpoints: report as tested, no ESBL editing) |
| `SPEC-URN` | CLSI M100 Ed36 Table 1 ('U' = urinary isolates only) |
| `REP-GPO-GN` | CLSI M100 Ed36 Appendix B1 / B2 (Gram-negative: glycopeptides, oxazolidinones, daptomycin) |

## تصحيحات استشهاد اتلقت أثناء المراجعة

- أرقام جداول EUCAST v3.3 كانت مزاحة: الوثيقة نفسها بترقّم **1 = Enterobacterales، 2 = non-fermenters، 3 = Gram-negative تانية، 4 = Gram-positive، 5 = anaerobes**. الكود كان كاتب «Table 2» للـ Enterobacterales و «Table 3» للـ Pseudomonas. اتصلّحت في 10 صفوف (`locus_corrected` في كل صف) — تصحيح استشهاد بس، والمضمون الموقَّع زي ما هو.
- نصوص «report as tested (EUCAST v16)» في قواعد العلاج بقت «CLSI M100 Ed36 Table 3A».
- مراجع لوحة الـ QC (`ast_reportability`، `ast_qa_engine`، `ast_consistency`، `inline_qc`) بقت CLSI أولاً.

## يحتاج توقيع د. طارق

- الصفوف الـ 3 اللي اتغيّرت (`intr_serratia` محتفظ بتوقيعه لأن نصه الموقَّع ما كانش بيذكر التتراسيكلين؛ `nobp_cefoperazone` **اتسحب توقيعه** لأن مضمونه اتغيّر؛ `nobp_cefoperazone_non_enterobacterales` جديد).
- مواضع CLSI المكتوبة في الجدول: CLSI M100 وثيقة مرخّصة، فمحتاجة قراءة من النسخة الأصلية قبل التوقيع.
- **ملاحظة:** معيار Cefoperazone للـ Enterobacterales اتأكّد من ملخص منشور (CLSI 2019 في PMC9617991) ومن جدول الأدوية المؤرشفة؛ لو نسخة Ed36 عند المعمل ما فيهاش المعيار، القرار يرجع «بلا breakpoint».
## ذِكر EUCAST خارج السجل (معلومة إضافية، مش قاعدة)

| المكان | ليه فضل |
|---|---|
| Fusidic acid (QC + profiles) | CLSI **مالوش** breakpoints لـ fusidic acid خالص — EUCAST هو المصدر الوحيد |
| Temocillin (Staph) | CLSI مالوش معايير temocillin |
| Pivmecillinam مع Klebsiella / Proteus | تحذير «بلا معيار CLSI» + جملة إن EUCAST بيمد الـ mecillinam للأنواع دي (قرار مفتوح للمعمل — ملف D5) |
| Fosfomycin IV | المعيار الوحيد المتاح FDA STIC / EUCAST IV (E. coli) |
| Serratia tetracycline / tigecycline | بقت **تحذير** علاجي بيذكر EUCAST بدل منع |
