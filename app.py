import streamlit as st
import google.generativeai as genai
import os
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="Phòng khám Thuế AI (Pro)", page_icon="🏥", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .main-header {text-align: center; font-size: 26px; font-weight: bold; color: #d32f2f; margin-bottom: 20px;}
    .error-msg {background-color: #ffebee; padding: 10px; border-radius: 5px; color: #b71c1c; border: 1px solid #ffcdd2;}
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM HỆ THỐNG ---
def get_api_key():
    if "GOOGLE_API_KEY" in st.secrets: return st.secrets["GOOGLE_API_KEY"]
    try: import toml; return toml.load(".streamlit/secrets.toml")["GOOGLE_API_KEY"]
    except: return None

def get_local_pdf_files(folder_path="tailieu"):
    if not os.path.exists(folder_path): return []
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

@st.cache_resource(show_spinner="Đang kết nối dữ liệu lớn...")
def initialize_knowledge_base(_api_key):
    genai.configure(api_key=_api_key)
    local_files = get_local_pdf_files()
    if not local_files: return None, "Thư mục 'tailieu' trống."

    try: remote_files = {f.display_name: f for f in genai.list_files()}
    except: remote_files = {}

    final_refs = []
    print(f"--- BẮT ĐẦU NẠP {len(local_files)} FILE ---")

    for path in local_files:
        name = os.path.basename(path)
        if name in remote_files:
            final_refs.append(remote_files[name])
        else:
            print(f"⬆️ Tải lên: {name}")
            try:
                ref = genai.upload_file(path, mime_type="application/pdf")
                # Chờ xử lý (Tăng timeout lên 90s cho file nặng)
                start_wait = time.time()
                while ref.state.name == "PROCESSING":
                    if time.time() - start_wait > 90: break
                    time.sleep(2)
                    ref = genai.get_file(ref.name)
                if ref.state.name == "ACTIVE": final_refs.append(ref)
                time.sleep(2)
            except Exception as e: print(f"Lỗi file {name}: {e}")

    # Cấu hình Model PRO (Bộ nhớ 2 triệu token) & Tắt Safety
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    # Dùng bản 1.5 PRO để chứa hết 23 file
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro", 
        safety_settings=safety_settings,
        system_instruction="Bạn là Chuyên gia Thuế. Trả lời dựa trên văn bản đính kèm."
    )
    return model, final_refs

# --- 3. GIAO DIỆN CHÍNH ---
st.markdown('<div class="main-header">🏥 PHÒNG KHÁM THUẾ AI (DEBUG)</div>', unsafe_allow_html=True)

api_key = get_api_key()
if not api_key: st.stop()

try:
    model, refs = initialize_knowledge_base(api_key)
    
    with st.sidebar:
        st.success(f"Đã kết nối: {len(refs)} văn bản")
        if st.button("🔄 Reset Dữ liệu"):
            st.cache_resource.clear()
            st.rerun()

    if "chat" not in st.session_state:
        history = [{"role": "user", "parts": refs + ["Học thuộc."]}, {"role": "model", "parts": "OK."}]
        st.session_state.chat = model.start_chat(history=history)
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if prompt := st.chat_input("Nhập câu hỏi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            msg_box = st.empty()
            try:
                # In ra để biết đang xử lý
                msg_box.write("⏳ Đang suy nghĩ (Model Pro mất khoảng 5-10s)...")
                response = st.session_state.chat.send_message(prompt, stream=True)
                full_text = ""
                for chunk in response:
                    if chunk.text:
                        full_text += chunk.text
                        msg_box.markdown(full_text + "▌")
                msg_box.markdown(full_text)
                st.session_state.messages.append({"role": "assistant", "content": full_text})
                
            except Exception as e:
                # HIỆN LỖI CHI TIẾT RA MÀN HÌNH
                error_text = str(e)
                st.markdown(f'<div class="error-msg">❌ <b>LỖI HỆ THỐNG:</b><br>{error_text}</div>', unsafe_allow_html=True)
                
                # Phân tích lỗi giúp anh
                if "429" in error_text:
                    st.info("💡 Nguyên nhân: Gói Free của bản Pro chỉ cho phép 2 câu hỏi/phút. Anh hỏi nhanh quá nên bị chặn.")
                elif "400" in error_text:
                    st.info("💡 Nguyên nhân: Dữ liệu quá lớn hoặc file lỗi.")

except Exception as e:
    st.error(f"Lỗi khởi động: {e}")


