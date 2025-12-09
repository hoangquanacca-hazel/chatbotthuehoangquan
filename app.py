import streamlit as st
import google.generativeai as genai
import os

# --- 1. CẤU HÌNH TRANG WEB ---
st.set_page_config(page_title="Trợ lý Luật Thuế VN (Gen Z)", page_icon="🇻🇳", layout="wide")

st.markdown("""
<style>
    .stChatMessage {border-radius: 10px; padding: 10px; border: 1px solid #eee;}
    .main-header {font-size: 24px; font-weight: bold; color: #d9534f;}
</style>
""", unsafe_allow_html=True)

# --- 2. CẤU HÌNH BÊN TRÁI ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9502/9502602.png", width=80)
    st.title("⚙️ Cài đặt")
    
    # Khởi tạo biến api_key
    api_key = None
    
    # Kỹ thuật Try-Except: Thử tìm key, nếu lỗi thì bỏ qua
    try:
        if 'GOOGLE_API_KEY' in st.secrets:
            api_key = st.secrets['GOOGLE_API_KEY']
            st.success("✅ Đã kết nối API Key từ hệ thống.")
    except FileNotFoundError:
        # Lỗi này xảy ra khi chạy trên máy cá nhân mà chưa tạo file secrets.toml
        pass 
    except Exception:
        pass

    # Nếu không tìm thấy key trong hệ thống (do đang chạy trên máy tính), hiện ô nhập
    if not api_key:
        api_key = st.text_input("Nhập Google API Key:", type="password")
        st.caption("Gợi ý: Nhập mã AIza... của bạn vào đây.")

# --- 3. HÀM XỬ LÝ ---
def get_pdf_files(folder_path):
    """Lấy danh sách file PDF trong thư mục"""
    files = []
    if os.path.exists(folder_path):
        for f in os.listdir(folder_path):
            if f.lower().endswith('.pdf'):
                files.append(os.path.join(folder_path, f))
    return files

def upload_local_files_to_gemini(file_paths):
    """Upload file từ ổ cứng lên Google Gemini"""
    file_refs = []
    status_bar = st.status("Đang nạp dữ liệu luật...", expanded=True)
    
    for path in file_paths:
        file_name = os.path.basename(path)
        status_bar.write(f"📥 Đang đọc: {file_name}...")
        try:
            # Upload trực tiếp file từ đường dẫn
            ref = genai.upload_file(path, mime_type="application/pdf")
            file_refs.append(ref)
        except Exception as e:
            st.error(f"Lỗi file {file_name}: {e}")
            
    status_bar.update(label="✅ Đã nạp xong dữ liệu!", state="complete", expanded=False)
    return file_refs

# --- 4. LOGIC CHÍNH ---
st.markdown('<p class="main-header">🏛️ Trợ lý Luật Thuế Việt Nam (Dữ liệu 2024-2025)</p>', unsafe_allow_html=True)

# Tìm file trong thư mục 'tailieu'
local_folder = "tailieu"
pdf_files = get_pdf_files(local_folder)

if not pdf_files:
    st.error(f"⚠️ Không tìm thấy file PDF nào trong thư mục '{local_folder}'. Hãy copy file luật vào đó!")
    st.stop()
else:
    with st.expander(f"📚 Đang sử dụng {len(pdf_files)} văn bản luật (Bấm để xem chi tiết)"):
        for f in pdf_files:
            st.write(f"- {os.path.basename(f)}")

# Chỉ chạy khi có API Key
if api_key:
    try:
        genai.configure(api_key=api_key)
        
        # Kiểm tra session để không upload lại khi nhấn nút khác
        if "chat_session" not in st.session_state:
            
            # Upload file lên Gemini
            uploaded_refs = upload_local_files_to_gemini(pdf_files)
            
            # Cấu hình Prompt
            system_instruction = """
            Bạn là Chuyên gia Tư vấn Thuế (Tax Expert) dành cho người Việt Nam.
            Dữ liệu: Hãy trả lời CHỈ dựa trên các tài liệu PDF được cung cấp.
            Yêu cầu:
            1. Trích dẫn điều luật cụ thể (Ví dụ: Theo Điều 5, Khoản 2 Luật Thuế GTGT...).
            2. Nếu là Luật mới 2024/2025, hãy nhấn mạnh sự thay đổi so với luật cũ.
            3. Trả lời ngắn gọn, súc tích, dễ hiểu.
            """
            
            # Chọn Model xịn nhất của bạn
            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash", # Đã cập nhật theo model của bạn
                system_instruction=system_instruction
            )
            
            # Tạo lịch sử chat ban đầu
            history_content = ["Hãy ghi nhớ các tài liệu đính kèm này."]
            history_content.extend(uploaded_refs)
            
            st.session_state.chat_session = model.start_chat(history=[
                {"role": "user", "parts": history_content},
                {"role": "model", "parts": "Đã tiếp nhận toàn bộ văn bản luật. Tôi sẵn sàng giải đáp."}
            ])
            st.session_state.chat_history = []

        # --- GIAO DIỆN CHAT ---
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if user_query := st.chat_input("Hỏi về thuế TNCN, GTGT, bán hàng Shopee..."):
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)
            
            with st.chat_message("assistant"):
                box = st.empty()
                box.markdown("⏳ *Đang tra cứu...*")
                try:
                    response = st.session_state.chat_session.send_message(user_query)
                    box.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    box.error(f"Lỗi: {e}")

    except Exception as e:
        st.error(f"Lỗi kết nối API: {e}")
else:
    st.warning("⬅️ Vui lòng nhập API Key để bắt đầu.")