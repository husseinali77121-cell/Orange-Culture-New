# الخطوط اللي البرنامج بيرسم بيها

نفس الخطوط اللي النسخة الـ online بتستخدمها على Streamlit Cloud (من `packages.txt`)،
محطوطة هنا عشان نسخة الـ EXE (Windows، من غير نت) تطلع **بنفس الشكل بالظبط**.
من غيرها، Windows ما عندوش Noto ولا Amiri ولا DejaVu، فكان:

- الـ PDF بيترسم بخط Windows بديل (Times New Roman / Segoe UI) بدل Noto Serif / Noto Sans / Amiri.
- صورة الـ decision tree كانت بتنزل لخط Pillow الافتراضي (10 بكسل ثابت) — كلام صغير جداً ما يتقريش.

| الملف | بيتستخدم في |
|---|---|
| `NotoSerif-*.ttf` (4) | متن الـ PDF والعناوين وأسماء البكتيريا (italic) |
| `NotoSans-Regular/Bold.ttf` | الجداول والأرقام والجرعات في الـ PDF، وتقارير الـ pathogenicity والـ QA |
| `Amiri-Regular/Bold.ttf` | كل النص العربي في الـ PDF |
| `NotoNaskhArabic-Regular/Bold.ttf` | بديل للعربي لو Amiri ما اشتغلش |
| `DejaVuSans.ttf`, `DejaVuSans-Bold.ttf` | صورة الـ decision tree كلها، والرموز (✓ ✗ ⊘ ◆ ⚠) في الـ PDF |

`cdss/reports/fonts.py` بيلاقي المجلد ده (جنب البرنامج أو جوه الـ EXE) ويسجّل الخطوط
للـ PDF بـ `@font-face`، وصورة الـ decision tree بتقرا منه الأول.

## التراخيص
- Noto Serif / Noto Sans / Noto Naskh Arabic — SIL Open Font License 1.1 (`OFL-Noto.txt`)،
  من https://github.com/notofonts/notofonts.github.io (hinted TTF، v2.015 / v2.021).
- Amiri — SIL Open Font License 1.1 (`OFL-Amiri.txt`)، من https://github.com/google/fonts/tree/main/ofl/amiri (v1.002).
- DejaVu Sans 2.37 — Bitstream Vera license + public domain (`LICENSE-DejaVu.txt`).

كلها مسموح توزيعها مع البرنامج من غير تعديل. ما تغيّرش أسماء الملفات: الكود بيدوّر عليها بالاسم.
