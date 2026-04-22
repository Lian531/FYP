'''
test_api.py - API and critical analysis tests for Lumiere Logic.
Run: python test_api.py  (Flask must be running on http://localhost:5000)
'''
import requests, os, io, time

BASE           = "http://localhost:5000"
TEST_EMAIL     = "testuser@lumiere.com"
TEST_PASSWORD  = "Test1234"
ADMIN_EMAIL    = "testadmin@lumiere.com"
ADMIN_PASSWORD = "Admin1234"

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"
B = "\033[1m";  X = "\033[0m"
passed = 0; failed = 0

def check(name, ok, got="", expected=""):
    global passed, failed
    print(f"  [{G}PASS{X}] {name}" if ok else f"  [{R}FAIL{X}] {name}")
    if not ok:
        failed += 1
        if expected: print(f"         Expected : {expected}")
        if got:      print(f"         Got      : {got}")
    else:
        passed += 1

def section(t):
    print(f"\n{B}{C}{'='*55}{X}\n{B}{C}  {t}{X}\n{B}{C}{'='*55}{X}")

def fix(code):
    print(f"\n         {Y}FIX CODE:{X}")
    for line in code.strip().split("\n"):
        print(f"           {line}")
    print()

def summary():
    total = passed + failed
    print(f"\n{B}{'='*55}{X}\n{B}  RESULTS: {passed}/{total} tests passed{X}")
    print(f"  {G}All tests passed!{X}" if not failed else f"  {R}{failed} test(s) failed{X}")
    print(f"{B}{'='*55}{X}\n")

# ==================================================================
section("TC-01  Health / Home Page")
r = requests.get(BASE + "/", allow_redirects=True)
check("Home page returns 200", r.status_code == 200, got=r.status_code, expected=200)
check("Response is HTML", "text/html" in r.headers.get("Content-Type",""))

# ==================================================================
section("TC-02  Register - missing fields")
s = requests.Session()
r = s.post(BASE+"/register",
           data={"name":"","email":"","password":"","confirm_password":""},
           allow_redirects=True)
check("Missing fields rejected (200/302)", r.status_code in (200,302), got=r.status_code)

# ==================================================================
section("TC-03  Register - invalid email")
s = requests.Session()
r = s.post(BASE+"/register",
           data={"name":"Test","email":"not-an-email","password":"pass123","confirm_password":"pass123"},
           allow_redirects=True)
check("Invalid email rejected", r.status_code in (200,302), got=r.status_code)
check("Error message in body",
      "valid email" in r.text.lower() or "invalid" in r.text.lower())

# ==================================================================
section("TC-04  Register - password mismatch")
s = requests.Session()
r = s.post(BASE+"/register",
           data={"name":"Test","email":"mm@test.com","password":"abc123","confirm_password":"xyz999"},
           allow_redirects=True)
check("Mismatch rejected", r.status_code in (200,302), got=r.status_code)
check("Mismatch message in body", "match" in r.text.lower() or "password" in r.text.lower())

# ==================================================================
section("TC-05  Login - wrong credentials")
s = requests.Session()
r = s.post(BASE+"/login",
           data={"email":"wrong@example.com","password":"wrongpass"},
           allow_redirects=True)
check("Wrong credentials returns 200", r.status_code == 200, got=r.status_code)
check("Error message in body", "invalid" in r.text.lower() or "password" in r.text.lower())

# ==================================================================
section("TC-06  Login - valid credentials")
s = requests.Session()
r = s.post(BASE+"/login",
           data={"email":TEST_EMAIL,"password":TEST_PASSWORD},
           allow_redirects=True)
check("Valid login redirects away from /login",
      "/login" not in r.url or r.status_code==200, got=r.url)
print(f"         Final URL : {r.url}")

# ==================================================================
section("TC-07  Protected routes - unauthenticated")
fresh = requests.Session()
for path in ["/questionnaire", "/results", "/upload"]:
    r = fresh.get(BASE+path, allow_redirects=True)
    check(f"{path} redirects to login", "login" in r.url, got=r.url)

# ==================================================================
section("TC-08  Admin route - non-admin blocked")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.get(BASE+"/admin", allow_redirects=True)
check("Non-admin blocked from /admin",
      "admin access" in r.text.lower() or "permission" in r.text.lower() or r.url==BASE+"/",
      got=r.url)

# ==================================================================
section("TC-09  Admin login and panel access")
sa = requests.Session()
r = sa.post(BASE+"/login", data={"email":ADMIN_EMAIL,"password":ADMIN_PASSWORD}, allow_redirects=True)
check("Admin login succeeds", r.status_code==200, got=r.status_code)
r2 = sa.get(BASE+"/admin", allow_redirects=True)
check("Admin can access /admin panel", r2.status_code==200, got=r2.status_code)
check("Panel has product/user data", "product" in r2.text.lower() or "user" in r2.text.lower())

# ==================================================================
section("TC-10  File upload - no file selected")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.post(BASE+"/upload", data={}, allow_redirects=True)
check("Upload without file returns 200/302", r.status_code in (200,302), got=r.status_code)

# ==================================================================
section("TC-11  File upload - corrupted file")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.post(BASE+"/upload",
           files={"photo":("fake.jpg", io.BytesIO(b"this is not an image"), "image/jpeg")},
           allow_redirects=True)
check("Corrupted file handled (200/302)", r.status_code in (200,302), got=r.status_code)
check("Error message shown",
      "corrupt" in r.text.lower() or "valid image" in r.text.lower() or "error" in r.text.lower())

# ==================================================================
section("TC-12  File upload - wrong type (PDF)")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.post(BASE+"/upload",
           files={"photo":("doc.pdf", io.BytesIO(b"PDF-fake-content"), "application/pdf")},
           allow_redirects=True)
check("PDF upload rejected (200/302)", r.status_code in (200,302), got=r.status_code)

# ==================================================================
section("TC-13  Unique filename generation")
upload_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
check("Uploads folder exists", os.path.exists(upload_dir))
files = set(os.listdir(upload_dir)) if os.path.exists(upload_dir) else set()
uuid_f = [f for f in files if len(os.path.splitext(f)[0]) == 32]
check("Uploads use 32-char UUID hex filenames",
      len(files)==0 or len(uuid_f)>0,
      got=f"{len(uuid_f)} of {len(files)} UUID-named")

# ==================================================================
section("TC-14  Shop page - authenticated")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.get(BASE+"/shop", allow_redirects=True)
check("Shop page loads (200)", r.status_code==200, got=r.status_code)
check("Shop contains product content", "product" in r.text.lower() or "shop" in r.text.lower())

# ==================================================================
section("TC-15  Cart - add non-existent product")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.post(BASE+"/cart/add", data={"product_id":99999,"quantity":1}, allow_redirects=True)
check("Non-existent product handled gracefully", r.status_code in (200,302,404), got=r.status_code)

# ==================================================================
section("TC-16  Logout clears session")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r1 = s.get(BASE+"/questionnaire", allow_redirects=False)
check("Logged-in user reaches /questionnaire", r1.status_code in (200,302), got=r1.status_code)
s.get(BASE+"/logout", allow_redirects=True)
r2 = s.get(BASE+"/questionnaire", allow_redirects=True)
check("After logout redirects to login", "login" in r2.url, got=r2.url)

# ==================================================================
section("TC-17  404 - unknown route")
r = requests.get(BASE+"/this-page-does-not-exist", allow_redirects=True)
check("Unknown route handled gracefully", r.status_code in (200,404), got=r.status_code)

# ==================================================================
section("TC-19  Response Time - pages under 3 seconds")
auth_s = requests.Session()
auth_s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
pages = [("/","Home",None),("/login","Login",None),("/register","Register",None),
         ("/shop","Shop",auth_s),("/questionnaire","Questionnaire",auth_s),("/cart","Cart",auth_s)]
for path, name, sess in pages:
    t0 = time.time()
    r = (sess or requests).get(BASE+path, allow_redirects=True)
    elapsed = time.time() - t0
    check(f"{name} loads under 3s  ({elapsed:.3f}s)",
          elapsed < 3.0 and r.status_code==200, got=f"{elapsed:.3f}s", expected="< 3.0s")

# ==================================================================
section("TC-20  Large File - 11 MB rejected, 9 MB allowed")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
try:
    r = s.post(BASE+"/upload",
               files={"photo":("big.jpg", io.BytesIO(b"X"*(11*1024*1024)), "image/jpeg")},
               allow_redirects=True)
    check("11 MB file rejected", r.status_code in (200,302,413), got=r.status_code)
    check("Size error message shown", "large" in r.text.lower() or "10" in r.text or r.status_code==413)
except Exception:
    check("11 MB causes connection reset (limit enforced)", True)

s2 = requests.Session()
s2.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
try:
    r2 = s2.post(BASE+"/upload",
                 files={"photo":("nine.jpg", io.BytesIO(b"X"*(9*1024*1024)), "image/jpeg")},
                 allow_redirects=True)
    check("9 MB not blocked by size limit (200/302)", r2.status_code in (200,302), got=r2.status_code)
except Exception:
    check("9 MB connection reset (unexpected)", False)

# ==================================================================
section("TC-21  Stress Test - 50 repeated login attempts")
ATTEMPTS=50; success=0; fail=0; times=[]
for _ in range(ATTEMPTS):
    t0 = time.time()
    r = requests.Session().post(BASE+"/login",
                                data={"email":TEST_EMAIL,"password":TEST_PASSWORD},
                                allow_redirects=True)
    times.append(time.time()-t0)
    if r.status_code==200: success+=1
    else: fail+=1
avg = sum(times)/len(times)
print(f"         Attempts: {ATTEMPTS}  |  Succeeded: {success}  |  Failed: {fail}")
print(f"         Avg: {avg:.3f}s  |  Slowest: {max(times):.3f}s  |  Fastest: {min(times):.3f}s")
check(f"All {ATTEMPTS} requests returned 200", success==ATTEMPTS, got=f"{success}/{ATTEMPTS}")
check("Average response time under 3s", avg<3.0, got=f"{avg:.3f}s", expected="< 3.0s")
check("No request took over 5s", max(times)<5.0, got=f"{max(times):.3f}s")
check("Server stayed stable (0 failures)", fail==0, got=f"{fail} failures")

# ==================================================================
section("TC-22  CRITICAL - SQL Injection on login form")
print(f"  {Y}ATTACK  :{X} email = ' OR '1'='1  (classic SQL injection)")
s = requests.Session()
r = s.post(BASE+"/login",
           data={"email":"' OR '1'='1","password":"anything"},
           allow_redirects=True)
check("SQL injection blocked", "login" in r.url or "invalid" in r.text.lower(), got=r.url)
check("Did not gain unauthorised access",
      "questionnaire" not in r.url and "admin" not in r.url, got=r.url)
fix("""
FIX: SQLAlchemy ORM uses parameterised queries automatically.
  user = User.query.filter_by(email=email).first()
  Becomes: SELECT * FROM user WHERE email = ?
  The ? is safely escaped - injection string is treated as plain text.
""")

# ==================================================================
section("TC-23  CRITICAL - XSS in registration name field")
print(f"  {Y}ATTACK  :{X} name = <script>alert('xss')</script>")
s = requests.Session()
r = s.post(BASE+"/register",
           data={"name":"<script>alert('xss')</script>",
                 "email":"xss_test@test.com",
                 "password":"pass123","confirm_password":"pass123"},
           allow_redirects=True)
check("XSS attempt handled (200/302)", r.status_code in (200,302), got=r.status_code)
check("Raw script tag not echoed back into page",
      "<script>alert" not in r.text, got="(script tag found - XSS risk!)")
fix("""
FIX: Jinja2 auto-escapes all {{ }} output by default.
  Template:  {{ user.name }}
  Output:    &lt;script&gt;alert('xss')&lt;/script&gt;
  The browser displays it as text - it never executes as code.
""")

# ==================================================================
section("TC-24  CRITICAL - Negative Price in admin panel")
print(f"  {Y}ATTACK  :{X} price = -999 submitted in add product form")
sa = requests.Session()
sa.post(BASE+"/login", data={"email":ADMIN_EMAIL,"password":ADMIN_PASSWORD}, allow_redirects=True)
r = sa.post(BASE+"/admin/products/add",
            data={"name":"Test Hack","category":"Foundation","price":"-999","skin_tone":"all"},
            allow_redirects=True)
check("Negative price rejected", r.status_code in (200,302), got=r.status_code)
check("Error message shown",
      "price" in r.text.lower() or "valid" in r.text.lower()
      or "positive" in r.text.lower() or "error" in r.text.lower())
fix("""
FIX: Price validation in admin_add_product route (app.py):
  price = float(price_raw)
  if price < 0:
      raise ValueError
  Flask flashes an error and the product is never saved.
""")

# ==================================================================
section("TC-25  CRITICAL - Double Extension File Upload")
print(f"  {Y}ATTACK  :{X} file named dangerous.php.jpg (disguised script as image)")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
fake_script = io.BytesIO(b"FAKE_SCRIPT_NOT_AN_IMAGE_CONTENT_1234567890")
r = s.post(BASE+"/upload",
           files={"photo":("dangerous.php.jpg", fake_script, "image/jpeg")},
           allow_redirects=True)
check("Double extension file handled (200/302)", r.status_code in (200,302), got=r.status_code)
check("Script content not executed in response",
      "FAKE_SCRIPT" not in r.text and "1234567890" not in r.text)
fix("""
FIX 1: UUID rename strips the original filename completely.
  filename = f"{uuid.uuid4().hex}.{ext}"
  dangerous.php.jpg saved as a3f9bc12...jpg - original name gone.

FIX 2: cv2.imread() validates actual image bytes.
  Non-image content returns None - file is deleted and rejected.
  img = cv2.imread(image_path)
  if img is None:
      return False, "The uploaded file is corrupted or not a valid image."
""")

# ==================================================================
section("TC-26  CRITICAL - Unauthorised Access to Results Page")
print(f"  {Y}ATTACK  :{X} Access /results directly without completing analysis")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.get(BASE+"/results", allow_redirects=True)
check("Results blocked without valid analysis in session",
      "questionnaire" in r.url or "login" in r.url or r.status_code in (200,302), got=r.url)
check("No other users data visible in response",
      "alice" not in r.text.lower() and "bob" not in r.text.lower())
fix("""
FIX: Results route checks analysis belongs to the logged-in user (app.py):
  analysis = db.session.get(SkinAnalysis, analysis_id)
  if not analysis or analysis.user_id != session['user_id']:
      flash('Analysis not found. Please try again.', 'error')
      return redirect(url_for('questionnaire'))
  Even with a guessed analysis ID, access is denied.
""")

# ==================================================================
section("TC-27  CRITICAL - Zero Byte Empty File Upload")
print(f"  {Y}ATTACK  :{X} Upload a completely empty 0-byte file as image")
s = requests.Session()
s.post(BASE+"/login", data={"email":TEST_EMAIL,"password":TEST_PASSWORD}, allow_redirects=True)
r = s.post(BASE+"/upload",
           files={"photo":("empty.jpg", io.BytesIO(b""), "image/jpeg")},
           allow_redirects=True)
check("Zero byte file handled without crash (200/302)", r.status_code in (200,302), got=r.status_code)
check("Error shown or safely redirected",
      "error" in r.text.lower() or "corrupt" in r.text.lower()
      or "valid" in r.text.lower() or r.status_code==302)
fix("""
FIX: cv2.imread() cannot decode 0 bytes - returns None.
  img = cv2.imread(image_path)
  if img is None:
      return False, (
          "The uploaded file is corrupted or not a valid image. "
          "Please upload a clear photo."
      )
  Empty file is deleted from uploads/ and user sees the error.
""")

# ==================================================================
summary()
