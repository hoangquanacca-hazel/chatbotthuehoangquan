import streamlit as st
import google.generativeai as genai
import os
import time

# --- 1. CẤU HÌNH TRANG (GIAO DIỆN CHUYÊN NGHIỆP) ---
st.set_page_config(
    page_title="Hệ thống Chuyên gia Thuế AI",
    page_icon="⚖️",
    layout="centered", # Dùng centered cho giống chat app mobile
    initial_sidebar_state="collapsed" # Ẩn sidebar cho gọn
)

# CSS để ẩn các thành phần thừa, làm đẹp giao diện
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stChatMessage {border-radius: 15px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
    .main-header {text-align: center; font-size: 28px; font-weight: 800; color: #1E88E5; margin-bottom: 20px;}
    .sub-header {text-align: center; font-size: 14px; color: #666; margin-bottom: 30px;}
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM HỆ THỐNG (CORE SYSTEM) ---

def get_api_key():
    """Lấy API Key từ Secrets (Ưu tiên) hoặc File local"""
    if "GOOGLE_API_KEY" in st.secrets:
        return st.secrets["GOOGLE_API_KEY"]
    return None

def get_local_pdf_files(folder_path="tailieu"):
    """Quét thư mục tailieu"""
    if not os.path.exists(folder_path):
        return []
    return [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

# 🔥 CACHE RESOURCE: Trái tim của hệ thống
# Hàm này chỉ chạy 1 lần duy nhất khi Server khởi động.
# Nó upload file và giữ kết nối trong bộ nhớ RAM của Server.
@st.cache_resource(show_spinner="Đang khởi tạo hệ tri thức Thuế (Lần đầu sẽ mất khoảng 1 phút)...")
def initialize_knowledge_base(_api_key):
    genai.configure(api_key=_api_key)
    
    # 1. Lấy file từ ổ cứng server (do GitHub đẩy sang)
    local_files = get_local_pdf_files()
    if not local_files:
        return None, "Không tìm thấy tài liệu trong thư mục 'tailieu'."

    # 2. Kiểm tra file trên Google (để tránh upload lại)
    uploaded_refs = []
    existing_files = {f.display_name: f for f in genai.list_files()}
    
    # Thanh tiến trình ẩn (chỉ hiện log trong console server)
    print(f"Bắt đầu đồng bộ {len(local_files)} văn bản luật...")

    for path in local_files:
        file_name = os.path.basename(path)
        
        if file_name in existing_files:
            # File đã có -> Dùng luôn
            uploaded_refs.append(existing_files[file_name])
            print(f"   [OK] Đã có: {file_name}")
        else:
            # File chưa có -> Upload
            print(f"   [UP] Đang tải: {file_name}...")
            try:
                ref = genai.upload_file(path, mime_type="application/pdf")
                # Chờ file xử lý xong
                while ref.state.name == "PROCESSING":
                    time.sleep(1)
                    ref = genai.get_file(ref.name)
                uploaded_refs.append(ref)
                time.sleep(1) # Nghỉ nhẹ tránh spam
            except Exception as e:
                print(f"   [ERR] Lỗi file {file_name}: {e}")

    # 3. Khởi tạo Model với dữ liệu đã nạp
    system_instruction = """
    Bạn là Chuyên gia Thuế - Kế toán - Hải quan cấp cao tại Việt Nam (Tax Counsel).
    Bạn đang sở hữu một kho dữ liệu pháp luật khổng lồ được đính kèm.
    
    NHIỆM VỤ:
    - Giải đáp thắc mắc dựa trên các văn bản luật đã học.
    - Phong cách: Chuyên nghiệp, Chính xác, Trích dẫn điều luật cụ thể.
    - Nếu câu hỏi nằm ngoài phạm vi tài liệu, hãy dùng kiến thức chung nhưng cảnh báo người dùng.
    """
    
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash", # Dùng bản Flash cho nhanh và bộ nhớ lớn
        system_instruction=system_instruction
    )
    
    return model, uploaded_refs

# --- 3. GIAO DIỆN CHÍNH (MAIN APP) ---

# Tiêu đề
st.markdown('<div class="main-header">🏛️ PHÒNG KHÁM THUẾ AI</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Hệ thống hỗ trợ pháp lý tự động dành cho SME & Hộ kinh doanh</div>', unsafe_allow_html=True)

# Kiểm tra API Key
api_key = get_api_key()
if not api_key:
    st.error("⚠️ Chưa cấu hình API Key. Vui lòng thêm vào Secrets.")
    st.stop()

# Khởi động não bộ (Chỉ chạy lần đầu, các lần sau lấy từ Cache -> Siêu nhanh)
try:
    model, knowledge_refs = initialize_knowledge_base(api_key)
    
    if isinstance(model, str): # Nếu trả về chuỗi nghĩa là có lỗi
        st.warning(model)
        st.stop()
        
    # Quản lý hội thoại
    if "chat_session" not in st.session_state:
        # Nạp lịch sử lần đầu gồm toàn bộ file luật
        history_setup = [{"role": "user", "parts": knowledge_refs + ["Hãy ghi nhớ toàn bộ văn bản luật này để tư vấn."]},
                         {"role": "model", "parts": "Tôi đã tiếp nhận toàn bộ cơ sở dữ liệu luật. Sẵn sàng phục vụ."}]
        st.session_state.chat_session = model.start_chat(history=history_setup)
        st.session_state.messages = [] # Chỉ hiển thị đoạn chat mới, ẩn đoạn nạp file đi

except Exception as e:
    st.error(f"Lỗi khởi động hệ thống: {e}")
    st.stop()

# Hiển thị hội thoại
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Ô nhập liệu (Nằm dưới cùng)
if prompt := st.chat_input("Nhập câu hỏi của bạn (Ví dụ: Thuế khoán năm 2025 tính thế nào?)..."):
    # Hiện câu hỏi
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Xử lý trả lời
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("⚡ *Đang tra cứu dữ liệu...*")
        try:
            response = st.session_state.chat_session.send_message(prompt)
            message_placeholder.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            message_placeholder.error("Hệ thống đang quá tải, vui lòng thử lại sau giây lát.")
