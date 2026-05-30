import streamlit as st
import pandas as pd
import re
import feedparser
from PIL import Image
import easyocr
import openai

# 初始化 EasyOCR
@st.cache_resource
def load_ocr():
    return easyocr.Reader(['ch_tra', 'en'])

try:
    reader = load_ocr()
except Exception as e:
    reader = None

def extract_stock_codes(image):
    if reader is None:
        return []
    results = reader.readtext(image)
    detected_text = " ".join([res[1] for res in results])
    stock_codes = re.findall(r'\b\d{4}\b', detected_text)
    return list(set(stock_codes))

def fetch_stock_news(stock_code):
    rss_url = f"https://tw.stock.yahoo.com/rss/s/{stock_code}"
    feed = feedparser.parse(rss_url)
    news_list = []
    for entry in feed.entries[:5]:
        news_list.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published if hasattr(entry, 'published') else "時間未提供"
        })
    return news_list

def generate_ai_report(stock_code, news_list, api_key):
    if not api_key:
        return "（請在左側輸入 OpenAI API 金鑰以產生 AI 摘要報告）"
    
    openai.api_key = api_key
    news_context = ""
    for idx, news in enumerate(news_list):
        news_context += f"新聞 {idx+1}: {news['title']}\n"
    
    prompt = f"""
    你是一位專業的台灣股市分析師。以下是股票代碼 {stock_code} 的最新新聞標題：
    {news_context}
    
    請為投資人針對這檔個股撰寫一份簡短的「每日市場觀點簡報」，包含：
    1. 今日消息面焦點（用簡單一兩句話概括主要事件）。
    2. 整體消息偏向正面、負面還是中立。
    請用繁體中文撰寫，條理分明。
    """
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo", 
            messages=[
                {"role": "system", "content": "你充當專業的繁體中文股市分析助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message['content']
    except Exception as e:
        return f"AI 報告生成失敗，請確認 API Key 是否正確。錯誤原因: {str(e)}"

# 網頁介面
st.set_page_config(page_title="台股每日 AI 智能情報站", layout="wide")
st.title("📈 台股每日 AI 智能情報站")

with st.sidebar:
    st.header("⚙️ 系統設定")
    openai_api_key = st.text_input("OpenAI API 金鑰", type="password", help="請至 OpenAI 官網申請 API Key")
    st.markdown("---")
    user_email = st.text_input("訂閱客戶 Email (測試用)", placeholder="client@example.com")

tab1, tab2 = st.tabs(["1. 選擇/辨識股票", "2. 生成與預覽報告"])

if 'selected_stocks' not in st.session_state:
    st.session_state.selected_stocks = []

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("手動輸入代號")
        manual_input = st.text_input("輸入股票代碼（多個請用英文逗號隔開）", placeholder="例如: 2330, 3711")
        if st.button("加入清單"):
            codes = [code.strip() for code in manual_input.split(",") if code.strip().isdigit()]
            st.session_state.selected_stocks = list(set(st.session_state.selected_stocks + codes))
            st.success(f"已加入：{codes}")
            
    with col2:
        st.subheader("上傳表格照片辨識")
        uploaded_file = st.file_uploader("上傳含有股票代號的圖片", type=["png", "jpg", "jpeg"])
        if uploaded_file is not None:
            image = Image.open(uploaded_file)
            st.image(image, caption='已上傳圖片', use_column_width=True)
            if st.button("開始辨識圖片中股票"):
                with st.spinner("正在辨識中..."):
                    detected_codes = extract_stock_codes(image)
                    if detected_codes:
                        st.session_state.selected_stocks = list(set(st.session_state.selected_stocks + detected_codes))
                        st.success(f"成功辨識並加入：{detected_codes}")
                    else:
                        st.warning("未能偵測到 4 位數代碼，請嘗試手動輸入。")

    st.markdown("---")
    st.write("📊 **目前訂閱的個股清單：**")
    if st.session_state.selected_stocks:
        st.info(", ".join(st.session_state.selected_stocks))
        if st.button("清空清單"):
            st.session_state.selected_stocks = []
            st.success("清單已清空")
    else:
        st.write("目前清單為空。")

with tab2:
    st.subheader("📑 每日整合報告預覽")
    if not st.session_state.selected_stocks:
        st.warning("請先回到第一步選擇或辨識股票。")
    else:
        if st.button("🚀 開始搜集資訊並生成 AI 報告"):
            full_report = ""
            for code in st.session_state.selected_stocks:
                st.markdown(f"### 🔍 股票代碼: {code}")
                news = fetch_stock_news(code)
                if news:
                    st.write("**最新新聞來源：**")
                    for n in news:
                        st.markdown(f"- [{n['title']}]({n['link']})")
                else:
                    st.write("暫無最新新聞。")
                
                ai_summary = generate_ai_report(code, news, openai_api_key)
                st.info(ai_summary)
                full_report += f"【股票代碼: {code}】\n{ai_summary}\n\n"
                st.markdown("---")
            
            if user_email:
                st.success(f"報告生成完畢！在正式發行版中，系統會將此報告發送至：{user_email}")
                st.text_area("郵件草稿內容：", full_report, height=150)
