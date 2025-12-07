import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import datetime
import math
import os
import json
import ephem 

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Chronos Oracle", page_icon="⏳", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #050505; color: #c0c0c0; }
    h1 { color: #fff; text-align: center; font-family: 'Courier New'; border-bottom: 1px solid #333; padding-bottom: 10px; }
    .stButton button { background-color: #333; color: white; border: 1px solid #fff; }
    .stTextInput input, .stDateInput input, .stTimeInput input { background-color: #111; color: #fff; border: 1px solid #555; }
</style>
""", unsafe_allow_html=True)

# --- ENGINE: PURE TIME CALCULATION ---

class ChronosEngine:
    @staticmethod
    def get_planet_positions(date_obj, time_obj):
        try:
            observer = ephem.Observer()
            observer.lat = '-6.2088'  # Jakarta
            observer.lon = '106.8456'
            observer.date = f"{date_obj} {time_obj}"
            
            planets = {
                "Sun": ephem.Sun(),
                "Moon": ephem.Moon(),
                "Mercury": ephem.Mercury(),
                "Venus": ephem.Venus(),
                "Mars": ephem.Mars(),
                "Jupiter": ephem.Jupiter(),
                "Saturn": ephem.Saturn()
            }
            
            results = {}
            zodiacs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

            for name, body in planets.items():
                body.compute(observer)
                ecl = ephem.Ecliptic(body)
                deg = math.degrees(ecl.lon)
                idx = int(deg / 30) % 12
                # Derajat presisi
                exact_deg = round(deg % 30, 2)
                results[f"{name}"] = f"{zodiacs[idx]} ({exact_deg}°)"

            # Ascendant (Rising Sign)
            ra_asc = observer.sidereal_time()
            deg_asc = math.degrees(ra_asc) 
            idx_asc = int((deg_asc + 90) / 30) % 12 
            results["Ascendant"] = zodiacs[idx_asc]

            return results
        except:
            return {"Error": "Astro Fail"}

    @staticmethod
    def get_weton_complex(date_obj):
        try:
            if date_obj.month <= 2:
                y = date_obj.year - 1
                m = date_obj.month + 12
            else:
                y = date_obj.year
                m = date_obj.month
            
            d = date_obj.day
            A = math.floor(y / 100)
            B = 2 - A + math.floor(A / 4)
            jdn = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + B - 1524.5
            
            anchor_jdn = 2455319 
            diff = int(jdn - anchor_jdn)
            
            pasaran_list = ['Legi', 'Pahing', 'Pon', 'Wage', 'Kliwon']
            pasaran = pasaran_list[(diff + 1) % 5]
            
            hari_list = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']
            hari = hari_list[date_obj.weekday()]
            
            neptu_hari = {'Minggu':5, 'Senin':4, 'Selasa':3, 'Rabu':7, 'Kamis':8, 'Jumat':6, 'Sabtu':9}
            neptu_pasaran = {'Legi':5, 'Pahing':9, 'Pon':7, 'Wage':4, 'Kliwon':8}
            neptu = neptu_hari[hari] + neptu_pasaran[pasaran]
            
            wuku_list = ["Sinta", "Landep", "Wukir", "Kurantil", "Tolu", "Gumbreg", "Warigalit", "Warigagung", "Julungwangi", "Sungsang", "Galungan", "Kuningan", "Langkir", "Mandasiya", "Julungpujut", "Pahang", "Kuruwelut", "Marakeh", "Tambir", "Medangkungan", "Maktal", "Wuye", "Manahil", "Prangbakat", "Bala", "Wugu", "Wayang", "Kulawu", "Dukut", "Watugunung"]
            wuku = wuku_list[math.floor(diff / 7) % 30]
            
            lakuning_map = {7:"Lakuning Pendito Sakti", 8:"Lakuning Geni", 9:"Lakuning Angin", 10:"Lakuning Pendito Mbangun Teki", 11:"Lakuning Setan", 12:"Lakuning Kembang", 13:"Lakuning Lintang", 14:"Lakuning Bulan", 15:"Lakuning Srengenge", 16:"Lakuning Bumi", 17:"Lakuning Gunung", 18:"Lakuning Paripurna"}
            lakuning = lakuning_map.get(neptu, "Unknown")

            return {
                "Pasaran": f"{hari} {pasaran}",
                "Neptu": neptu,
                "Wuku": wuku,
                "Lakuning": lakuning
            }
        except:
            return {"Pasaran": "Unknown"}

    @staticmethod
    def num_reduce(n):
        while n > 9 and n not in [11, 22, 33]:
            n = sum(int(d) for d in str(n))
        return n

    @staticmethod
    def calc_life_path(dob):
        total = dob.year + dob.month + dob.day
        return ChronosEngine.num_reduce(total)
    
    @staticmethod
    def get_shio(year):
        animals = ['Rat','Ox','Tiger','Rabbit','Dragon','Snake','Horse','Goat','Monkey','Rooster','Dog','Pig']
        elements = ['Metal','Metal','Water','Water','Wood','Wood','Fire','Fire','Earth','Earth']
        animal = animals[(year - 1900) % 12]
        element = elements[int(str(year)[-1])]
        return f"{element} {animal}"

# --- PDF GENERATOR ---

class ChronosPDF(FPDF):
    def header(self): pass
    def footer(self):
        self.set_y(-15)
        self.set_font('Courier', '', 8)
        self.set_text_color(100)
        self.cell(0, 10, f'Chronos Log - Page {self.page_no()}', 0, 0, 'C')

    def sanitize(self, text):
        replacements = {"\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"', "…": "..."}
        for char, safe_char in replacements.items(): text = text.replace(char, safe_char)
        return text.encode('latin-1', 'ignore').decode('latin-1')

    def make_cover(self, date_str):
        self.add_page()
        self.set_fill_color(10,10,10)
        self.rect(0,0,210,297,'F') 
        self.set_text_color(255, 255, 255) 
        self.set_font('Courier', 'B', 24)
        self.ln(80)
        self.cell(0, 10, "CHRONOS BLUEPRINT", 0, 1, 'C')
        self.ln(10)
        self.set_font('Courier', '', 14)
        self.cell(0, 10, "TIME-BASED SOUL ARCHITECTURE", 0, 1, 'C')
        self.ln(50)
        self.set_font('Courier', '', 10)
        self.cell(0, 10, f"Generated: {date_str}", 0, 1, 'C')
        self.set_text_color(0)

    def print_raw_data(self, data):
        self.add_page()
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, "PLANETARY & TIME DATA", 0, 1)
        self.ln(5)
        self.set_font('Courier', '', 10)
        json_str = json.dumps(data, indent=2)
        self.multi_cell(0, 5, self.sanitize(json_str))

    def print_analysis(self, body_text):
        self.add_page()
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, "ORACLE ANALYSIS", 0, 1)
        self.ln(5)
        self.set_font('Times', '', 12)
        clean_body = self.sanitize(body_text)
        self.multi_cell(0, 7, clean_body)

# --- MAIN ---

def send_email(to_email, pdf_filename):
    from_email = st.secrets["EMAIL_USER"]
    password = st.secrets["EMAIL_PASSWORD"]
    msg = MIMEMultipart()
    msg['From'] = "Chronos Oracle"
    msg['To'] = to_email
    msg['Subject'] = "Chronos Blueprint [No Name]"
    body = "Berikut adalah analisis murni berdasarkan Waktu Kelahiran Anda."
    msg.attach(MIMEText(body, 'plain'))
    with open(pdf_filename, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f"attachment; filename= {pdf_filename}")
    msg.attach(part)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_email, password)
    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()

def main():
    if "auth" not in st.session_state: st.session_state.auth = False
    if not st.session_state.auth:
        st.title("⏳ CHRONOS GATE")
        pwd = st.text_input("Access Code:", type="password")
        if st.button("UNLOCK"):
            if pwd == st.secrets["ACCESS_PASSWORD"]: st.session_state.auth = True; st.rerun()
            else: st.error("Denied.")
        return

    st.title("⏳ CHRONOS ORACLE")
    st.write("Analisis Murni Waktu (Tanpa Nama).")
    
    with st.form("data_form"):
        # HAPUS INPUT NAMA
        # GW UBAH TAHUNNYA JADI 1800 DAN DEFAULTNYA JADI 1990 BIAR GAK KE-RESET KE HARI INI
        dob = st.date_input("Tanggal Lahir", 
                            min_value=datetime.date(1, 1, 1), 
                            max_value=datetime.date(2100, 12, 31),
                            value=datetime.date(1990, 1, 1))
        tob = st.time_input("Waktu Lahir (WAJIB AKURAT)", value=datetime.time(12, 0))
        email = st.text_input("Email Penerima")
        go = st.form_submit_button("ANALISIS WAKTU")

    if go and email:
        with st.status("Reading the Stars...", expanded=True) as status:
            
            # HITUNG DATA MURNI WAKTU
            astro_data = ChronosEngine.get_planet_positions(dob, tob)
            weton = ChronosEngine.get_weton_complex(dob)
            life_path = ChronosEngine.calc_life_path(dob)
            shio = ChronosEngine.get_shio(dob.year)
            
            # STRUKTUR JSON FINAL (Tanpa Nama/Numerologi Nama)
            final_json = {
                "COSMIC_COORDINATES": {
                    "Date": str(dob),
                    "Time": str(tob),
                },
                "PLANETARY_POSITIONS": astro_data,
                "WETON_JAVA": weton,
                "CHINESE_ZODIAC": {
                    "Shio_Elemen": shio
                },
                "NUMEROLOGY_BIRTH": {
                    "Life_Path": life_path,
                    "Day_Number": ChronosEngine.num_reduce(dob.day)
                }
            }

            # AI PROCESS
            st.write("🧠 Connecting to Chronos...")
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            model = genai.GenerativeModel('gemini-flash-latest')

            json_str_clean = json.dumps(final_json, indent=0).replace("{", "{\n").replace("}", "\n}")

            prompt = f"""
            SYSTEM: You are CHRONOS, the Keeper of Time. 
            Do not analyze names. Analyze only the moment of birth.
            
            DATA:
            {json_str_clean}

            TASK:
            Provide a deep, raw, and highly accurate soul analysis based ONLY on the planetary positions and time cycles.
            Focus on the "Ascendant" (Rising Sign) and "Weton" interactions.
            Tell the user their core nature without the bias of their human name.
            
            FORMAT:
            No tables. Just pure, flowing wisdom. 1500 words approx. Gunakan Bahasa Indonesia Seluruhnya
            """

            response = model.generate_content(prompt)
            ai_text = response.text

            # PDF GENERATION
            st.write("📄 Printing Blueprint...")
            pdf = ChronosPDF()
            pdf.make_cover(str(datetime.date.today()))
            pdf.print_raw_data(final_json)
            pdf.print_analysis(ai_text)

            pdf_file = "Chronos_Blueprint.pdf"
            pdf.output(pdf_file)

            # KIRIM
            st.write("📨 Sending...")
            send_email(email, pdf_file)
            
            os.remove(pdf_file)
            status.update(label="Done.", state="complete", expanded=False)
            st.balloons()
            st.success("Terkirim! Murni Waktu.")

if __name__ == "__main__":
    main()