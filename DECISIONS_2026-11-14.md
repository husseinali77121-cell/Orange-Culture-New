# سجل القرارات — 2026-11-14 (تطبيق في v6.9)

**المصدر:** ملف `Orange-CDSS-decisions-v6.8.pdf` (16 صفحة) — رد مالك المعمل (د. حسين):
**«خذ بتوصيات CLSI & IDSA recommendations في كل حاجة»**.

> القرارات هنا قرارات **مالك المعمل**. كل صف إكلينيكي اتغيّر أو اتضاف بسببها متسجّل في
> `cdss/guidelines/guideline_registry.py` بختم `_OWNER_D` («NOT a clinician countersignature»)
> ومحطوط في طابور توقيع **د. طارق الشافعي**. ولا توقيع قديم اتنسب لمضمون جديد: صف
> `intr_acinetobacter` اتسحب توقيعه (`signature_withdrawn`) لأن مضمونه اتغيّر.

| البند | القرار | اتطبّق إزاي | المصدر |
|---|---|---|---|
| **D1** المرجع لقراءة النتيجة | **B — CLSI M100 Ed36 في كل حاجة** | معنى الـ I حسب الصنف والموقع (`therapy/clsi_categories.py`) · Acinetobacter: Tetracycline/Doxycycline «بلا breakpoint» بدل جوهري، Cefotaxime/Ceftriaxone يتبلّغوا + تحذير علاجي · شيل قاعدتي QC الخاصتين بـ EUCAST (Nitrofurantoin لغير E. coli، Imipenem للـ Proteeae) · CLSI أولاً في المراجع | CLSI M100 Ed36 (Instructions — تعريف I؛ Table 2B-2؛ Appendix B)؛ ملخصات Ed36 (Vastian 2026، laboratorytests.org)؛ PubMed 41628687 |
| **D2** Klebsiella aerogenes | **A — كائن مستقل بقواعد AmpC** | profile مستقل (AmpC متوسط الخطر) · صف مقاومة جوهرية · OCR · قائمة العينات · لوحة الـ QC | IDSA AMR Guidance 2026 (AmpC-E: E. cloacae complex، K. aerogenes، C. freundii، H. alvei) |
| **D3** الفلوروكينولون للأطفال | **B — تحذير حسب AAP 2016** | Ciprofloxacin / Levofloxacin تحت 18 = تحذير بملاحظة AAP؛ باقي الكينولونات ممنوعة | AAP Clinical Report 2016 (Pediatrics 138:e20162706) |
| **D4** فئة SDD | **دعم SDD (من غير إدخال MIC)** | خيار SDD في اللوحة والـ OCR · يُقرأ I في كل الحسابات · المحرك يكتب نظام جرعة الـ SDD | CLSI M100 Ed36 (SDD: Cefepime و Pip-Tazo للـ Enterobacterales، Ceftaroline لـ S. aureus، Daptomycin لـ E. faecium)؛ FDA STIC (Pip-Tazo) |
| **D5** أدوية IDSA 2026 الجديدة | **A — إضافة الخمسة** | Pivmecillinam · Sulopenem · Gepotidacin · Cefepime-enmetazobactam · Fosfomycin IV (`formulary/abx_guidelines.py`، `therapy/rules/new_agents.py`، الجداول) | IDSA AMR Guidance 2026 (Q1.1–1.4، AmpC-E، CRE)؛ نشرات FDA: Pivya 2024، Orlynvah 2024، Blujepa 2025، Exblifep 2024؛ Fomicyt SmPC؛ FDA STIC؛ WHO AWaRe 2025 |
| **D6** تصنيفات AWaRe | **A — زي ما هي** | الموجود ما اتغيّرش؛ الجديد: Pivmecillinam Access، Gepotidacin Watch، Fosfomycin IV Reserve (WHO 2025)؛ Sulopenem و Cefepime-enmetazobactam غير مصنّفين → Reserve | WHO AWaRe 2025 (aware.essentialmeds.org) |
| **T1** 4 قواعد QC (v6.6) | **معتمدة بقرار المالك** — تنتظر توقيع د. طارق | `owner_approved` على الصفوف الأربعة مع إبقاء `awaiting_countersignature` | متوافقة مع CLSI و IDSA |
| **T2** جمل التداخلات (v6.7) | تنتظر توقيع د. طارق | بدون تغيير (اتضاف لها 8 جمل للأدوية الجديدة من نشراتها) | النشرات |
| **T3** ملاحظات الحمل بالإنجليزي (v6.7) | تنتظر توقيع د. طارق | بدون تغيير (اتضاف لها 5 للأدوية الجديدة من نشراتها) | النشرات |
| **C1–C7** أحكام v6.7 | **موافق** (مطبّقة من v6.7) | — | كما في ملف القرارات |

## تغيير لقيته في IDSA 2026 أثناء المراجعة (اتطبّق ضمن «IDSA في كل حاجة»)

**AmpC + Cefepime SDD (MIC 4–8):** نص 2024 كان «احتمال ESBL ← Carbapenem». نص 2026 (Q2.3): Cefepime
مفضّل طالما MIC ≤ 8 ولم يُكتشف جين ESBL. اتعدّل في كل الأماكن؛ ولسه «تحذير» عشان جرعة الـ SDD (2 g q8h).

## ما يحتاج توقيع د. طارق الآن

1. صفوف السجل المعتمدة بقرار المالك (13): منها `intr_acinetobacter` و `intr_nonfermenter_unspeciated`
   و `nobp_tetracycline_doxycycline_acinetobacter` (D1)، والقواعد الأربعة في T1.
2. جرعات الأدوية الخمسة (`dose_owner_approved` — من النشرات).
3. T2 و T3 (والإضافات عليهم للأدوية الجديدة).
4. نصوص ملاحظات الـ I والـ SDD الجديدة (`therapy/clsi_categories.py`) وملاحظة AAP للأطفال.

## نقاط فضلت قرار إكلينيكي (اتاخدت بأحوط قراءة)

- **Pivmecillinam مع Klebsiella / Proteus:** CLSI عنده breakpoints لـ E. coli بس → «تحذير: بلا معيار
  CLSI» (EUCAST بيغطي Klebsiella وغيرها). لو المعمل هيقرا الـ mecillinam بـ EUCAST للأنواع دي، القرار
  يتغيّر لـ «مسموح».
- **Sulopenem و Cefepime-enmetazobactam في AWaRe:** مش مصنّفين في قائمة WHO 2025 → اتعاملوا Reserve
  (زي Sulbactam-durlobactam). ده بيأخّرهم في الترتيب بعد البدائل Access/Watch.
- **Gepotidacin بعد 12 سنة:** النشرة للإناث ≥12 سنة ووزن ≥40 kg — البرنامج بيسمح من 12 سنة ويكتب
  شرط الوزن والجنس في الملاحظة (ما بيقراش الوزن تلقائياً).

## تحديث 2026-11-19 (v7.0) — تطبيق D1 على باقي قواعد EUCAST

اتراجعت كل قاعدة أصلها EUCAST (التفاصيل في `EUCAST_AUDIT_2026-11-19.md`). تلات قواعد اتحولت لـ CLSI وتنتظر
توقيع د. طارق: Serratia tetracyclines (تحذير بدل منع)، Cefoperazone (معيار CLSI للـ Enterobacterales؛
Cefoperazone-sulbactam بلا breakpoint — اتسحب التوقيع القديم)، Serratia خرجت من قاعدة tigecycline.

**قرار مفتوح للمعمل:** Cefoperazone-sulbactam (Sulperazon) بقى **مش خيار علاجي** في كل الحالات لأنه مالوش
breakpoints في CLSI ولا EUCAST — زي ما لوحة الـ QC كانت بتقول من الأول. لو المعمل عايز يبلّغه بمعيار
محلي، ده محتاج قرار مكتوب.
