# رفع البرنامج في repo جديد

النسخة دي كاملة ومستقلة. مش محتاجة أي حاجة من الـ repo القديم، والـ repo القديم مش
محتاج يتغيّر فيه أي حاجة. الاتنين يفضلوا شغالين جنب بعض.

## 1. اعمل الـ repo

على GitHub: **New repository** ← اسم جديد (مثلاً `Orange-Culture-analyzer-v6`) ←
**Private** ← ما تعلّمش على "Add a README" ولا ".gitignore" ولا "license" (موجودين هنا
بالفعل) ← **Create repository**.

## 2. ارفع الملفات على دفعتين

GitHub بيقبل **100 ملف بس في المرة الواحدة** من المتصفح، والبرنامج 164 ملف.
فك الـ zip، وافتح المجلد `Orange-Culture-analyzer-main`، وبعدين:

| الدفعة | اسحب ده | عدد الملفات |
|---|---|---|
| **الأولى** | مجلد `cdss` لوحده | 81 |
| **التانية** | كل الباقي: `cdss_ui` · `tests` · `tools` · `.github` · `.devcontainer` · وكل الملفات اللي برّه المجلدات | 83 |

في كل دفعة: **Add file ← Upload files** ← اسحب المجلدات نفسها (مش اللي جواها) عشان
المسارات تفضل زي ما هي ← **Commit changes**.

⚠️ اتأكد إن `.github` و `.devcontainer` و `.gitignore` اترفعوا. أسماؤهم بتبدأ بنقطة، وفي
Mac بيبقوا مخفيين (اضغط `Cmd + Shift + .` عشان يظهروا). من غير `.github` مش هيبقى
فيه اختبارات تلقائية.

> **لو التطبيق اشتغل والرفع لسه ناقص** هيظهر خطأ `ModuleNotFoundError`. ارفع الملف الناقص
> والتطبيق هيرجع لوحده في أول تشغيل بعدها. لو لسه شايف شريط أحمر أو أصفر بعد ما الرفع
> كمل: **Manage app ← ⋮ ← Reboot app**.

## 3. اتأكد إن الرفع كامل

افتح تبويب **Actions** في الـ repo الجديد. بعد الدفعة التانية هيشتغل اتنين:

| الـ workflow | معناه |
|---|---|
| **CDSS Tests** ✅ | الاختبارات كلها عدّت على نسخة GitHub. أول خطوة فيه (**Guard 0**) بتسمّي أي ملف ناقص (MISSING) أو قديم (DIFFERS) أو في مكان غلط (EXTRA)، و**لو أي اختبار فشل افتح Guard 0 الأول** |
| **Build Windows EXE** ✅ | بنى الـ EXE واختبره. ملف الـ EXE في **Artifacts** تحت الـ run |

لو الاتنين خضر، يبقى الرفع كامل والـ EXE اتبنى صح.

## 4. Streamlit Cloud — تطبيق جديد

**Create app** ← اختار الـ repo الجديد ← Branch: `main` ← Main file: `streamlit_app.py` ←
**Advanced settings**:

- **Python version:** نفس اللي على التطبيق القديم.
- **Secrets:** انسخ محتوى Secrets من التطبيق القديم (Settings ← Secrets) والصقه هنا
  زي ما هو. البرنامج بيقرا المفاتيح دي:

| المفتاح | لازم؟ |
|---|---|
| `subscribers` (أو `subscribers_json`) | **لازم** — من غيره مفيش حد يقدر يدخل |
| `subscriber_hashes` | لازم لو بتستخدم كلمات سر |
| `lab_name` · `lab_city` | اختياري — اسم المعمل في التقارير |
| `vendor_phone` · `vendor_email` | اختياري |

التطبيق الجديد هياخد رابط جديد. الرابط القديم يفضل شغال على النسخة القديمة لحد ما
تقرر.

## 5. قبل ما تعتمد عليه

جرّب على التطبيق الجديد حالتين أو تلاتة تعرف نتيجتهم من النسخة القديمة، وخصوصاً:
مزرعة بول (لوحة "AST Quality Check" بقت بتظهر لها)، و Staph فيها Erythromycin R +
Clindamycin S (هيسألك عن الـ D-test). الفروق المقصودة كلها مكتوبة في
`CHANGELOG_2026-11-12.md`.

---

لو حبيت ترفع بـ git بدل المتصفح (مفيش حد 100 ملف):

```bash
cd Orange-Culture-analyzer-main
git init -b main
git add -A
git commit -m "Orange Culture Analyzer v6"
git remote add origin https://github.com/<اسمك>/<اسم-الrepo-الجديد>.git
git push -u origin main
```
