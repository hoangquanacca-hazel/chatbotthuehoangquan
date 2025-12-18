import streamlit as st
import google.generativeai as genai
import os
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Hệ thống Chuyên gia Thuế AI",
    page_icon="⚖️",
    layout="wide", # Đổi sang wide để hiển thị được nhiều thông tin hơn
    initial_sidebar_state="expanded" # Mở sidebar để xem danh sách file
)

# CSS làm đẹp
st.markdown("""
<style>
    .stChatMessage {border-radius: 15px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
    .main-header {text-align: center; font-size: 28px; font-weight: 800; color: #1E88E5; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM HỆ THỐNG ---

def get_api_key():
    # Thử lấy từ Secrets (Ưu tiên Cloud/Web)
    if "GOOGLE_API_KEY" in st.secrets:
        return st.secrets["GOOGLE_API_KEY"]
    # Thử lấy từ File local (Máy tính)
    try:
        import toml
        secrets = toml.load(".streamlit/secrets.toml")
        return secrets["GOOGLE_API_KEY"]
    except:
        return None

def get_local_pdf_files(folder_path="tailieu"):
    if not os.path.exists(folder_path):
        return []
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

# 🔥 CACHE RESOURCE: Nạp dữ liệu
@st.cache_resource(show_spinner="Đang khởi tạo hệ tri thức Thuế...")
def initialize_knowledge_base(_api_key):
    genai.configure(api_key=_api_key)
    
    local_files = get_local_pdf_files()
    if not local_files:
        return None, "⚠️ Thư mục 'tailieu' đang trống."

    uploaded_refs = []
    
    # Lấy danh sách file đã có trên Cloud
    try:
        existing_files = {f.display_name: f for f in genai.list_files()}
    except:
        existing_files = {}

    status_text = st.empty() 

    for path in local_files:
        file_name = os.path.basename(path)
        
        if file_name in existing_files:
            # File đã có -> Dùng luôn
            uploaded_refs.append(existing_files[file_name])
        else:
            # File chưa có -> Upload
            status_text.text(f"⬆️ Đang tải mới: {file_name}...")
            try:
                ref = genai.upload_file(path, mime_type="application/pdf")
                while ref.state.name == "PROCESSING":
                    time.sleep(1)
                    ref = genai.get_file(ref.name)
                uploaded_refs.append(ref)
                time.sleep(1) 
            except Exception as e:
                print(f"Lỗi: {e}")

    status_text.empty()

    # Khởi tạo Model
    system_instruction = """
    Bạn là Chuyên gia Thuế - Kế toán - Hải quan cấp cao tại Việt Nam.
    Dựa trên các văn bản luật được cung cấp, hãy tư vấn chính xác, trích dẫn điều luật.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", 
        system_instruction=system_instruction
    )
    
    return model, uploaded_refs

# --- 3. GIAO DIỆN CHÍNH ---

# SIDEBAR: HIỂN THỊ DANH SÁCH FILE (Để anh kiểm tra)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063822.png", width=80)
    st.title("🗂️ Dữ liệu đã nạp")
    
    if st.button("🔄 Bấm vào đây để Nạp lại Dữ liệu"):
        st.cache_resource.clear()
        st.rerun()
    
    st.divider()

# MAIN CONTENT
st.markdown('<div class="main-header">🏛️ PHÒNG KHÁM THUẾ AI</div>', unsafe_allow_html=True)

api_key = get_api_key()

if not api_key:
    api_key = st.text_input("Nhập API Key:", type="password")

if api_key:
    try:
        model, knowledge_refs = initialize_knowledge_base(api_key)
        
        if isinstance(model, str): 
            st.warning(model)
        else:
            # HIỂN THỊ DANH SÁCH FILE RA SIDEBAR
            with st.sidebar:
                st.success(f"Đang kết nối: {len(knowledge_refs)} văn bản")
                for ref in knowledge_refs:
                    st.caption(f"📄 {ref.display_name}")

            # Chat Logic
            if "chat_session" not in st.session_state:
                history_setup = [{"role": "user", "parts": knowledge_refs + ["Hãy ghi nhớ toàn bộ văn bản luật này."]},
                                 {"role": "model", "parts": "Đã tiếp nhận dữ liệu."}]
                st.session_state.chat_session = model.start_chat(history=history_setup)
                st.session_state.messages = []

            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            if prompt := st.chat_input("Nhập câu hỏi..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    box = st.empty()
                    box.markdown("⚡ *Đang tra cứu...*")
                    try:
                        response = st.session_state.chat_session.send_message(prompt)
                        box.markdown(response.text)
                        st.session_state.messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        box.error("Hệ thống đang bận. Vui lòng thử lại.")

    except Exception as e:
        st.error(f"Lỗi: {e}")
