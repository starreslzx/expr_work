import streamlit as st
from docx import Document
uploaded_file = st.file_uploader(
    label="Upload a file",
    type=["docx"],
    accept_multiple_files=False,
)
if uploaded_file is not None:
    st.write(f"文件名:{uploaded_file.name}")
    st.write(f"文件大小:{uploaded_file.size}")
    st.write(f"文件类型：{uploaded_file.type}")
    if uploaded_file.type=="docx":
        doc = Document(uploaded_file)
        full_text=[]
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                full_text.append(paragraph.text)
        doc_content='\n'.join(full_text)