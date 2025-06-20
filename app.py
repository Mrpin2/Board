import streamlit as st
import google.generativeai as genai
import PyPDF2
import io
from docx import Document
from PIL import Image # For image processing (required for OCR)
import pytesseract # For Optical Character Recognition (OCR)
from pdf2image import convert_from_bytes # For converting PDF pages to images

# --- Streamlit Secrets Configuration ---
# To use this application, you need to create a file named `.streamlit/secrets.toml`
# in the same directory as your `app.py` file for local development.
# For Streamlit Cloud, you configure these secrets directly in the app dashboard.
#
# # .streamlit/secrets.toml
# GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
# STREAMLIT_PASSWORD = "Rajeev"
# # OPENAI_API_KEY = "YOUR_OPENAI_API_KEY" # Uncomment and add if you plan to use OpenAI API later

# --- Password Protection ---
correct_password = st.secrets.get("STREAMLIT_PASSWORD")

if not correct_password:
    st.error("Password not found in Streamlit secrets. Please set `STREAMLIT_PASSWORD`.")
    st.stop()

password = st.sidebar.text_input("Enter Password to Access", type="password")

if password != correct_password:
    st.sidebar.error("Incorrect password. Please try again.")
    st.stop()
else:
    st.sidebar.success("Password accepted!")

st.title("📄 Meeting Synopsis from PDF (Powered by Gemini & OCR)")
st.write("Upload a meeting minutes PDF (text-based or scanned), and I'll generate a concise synopsis.")

# --- API Key Initialization ---
gemini_api_key = st.secrets.get("GEMINI_API_KEY")

if not gemini_api_key:
    st.error("Gemini API key not found in Streamlit secrets. Please set `GEMINI_API_KEY`.")
    st.stop()

try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    st.error(f"Error configuring Gemini API: {e}")
    st.stop()

# --- OCR Engine Path (Crucial for pytesseract - usually not needed on Streamlit Cloud if tesseract-ocr is in packages.txt) ---
# pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # Common path for Linux, might be needed if auto-detection fails

# --- PDF Processing Function ---
@st.cache_data # Cache the extraction to avoid re-processing on rerun
def extract_text_from_pdf(uploaded_file_buffer):
    """
    Extracts text from a PDF, attempting OCR if direct text extraction fails or pages are images.
    """
    text = ""
    pdf_file_bytes = uploaded_file_buffer.getvalue()
    pdf_file = io.BytesIO(pdf_file_bytes)

    # First, try PyPDF2 for text-based PDFs (faster and more accurate if text is present)
    st.info("Attempting direct text extraction with PyPDF2...")
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as e:
                st.warning(f"Could not extract direct text from page {page_num + 1}: {e}")
        
        if text.strip(): # If any text was extracted directly, use it
            st.success("Direct text extraction successful for some or all pages.")
            return text

    except Exception as e:
        st.error(f"Error reading PDF with PyPDF2: {e}")
        st.info("Falling back to OCR for all pages.")

    # If PyPDF2 extraction yielded no text or failed, proceed with OCR
    st.warning("No text extracted directly or an error occurred. Attempting OCR using pdf2image and pytesseract...")
    full_ocr_text = ""
    try:
        # Convert PDF pages to PIL Image objects
        # We need to specify the Poppler path if not in system PATH.
        # For Streamlit Cloud, after 'poppler-utils' is installed, it should be in PATH.
        images = convert_from_bytes(pdf_file_bytes)

        if not images:
            st.error("pdf2image could not convert any pages to images. PDF might be corrupted or malformed.")
            return ""

        for i, image in enumerate(images):
            with st.spinner(f"Performing OCR on page {i+1}/{len(images)}..."):
                try:
                    page_ocr_text = pytesseract.image_to_string(image)
                    if page_ocr_text:
                        full_ocr_text += page_ocr_text + "\n"
                except Exception as e:
                    st.warning(f"Error during OCR on page {i+1}: {e}")
        
        if not full_ocr_text.strip():
            st.error("OCR did not yield any text. The document might be very low quality or entirely image-based without readable text.")
            return ""
        
        return full_ocr_text

    except Exception as e:
        st.error(f"An error occurred during PDF-to-image conversion or OCR: {e}")
        st.info("Please ensure `tesseract-ocr` and `poppler-utils` are correctly installed via `packages.txt` on Streamlit Cloud, and `pdf2image` and `pytesseract` are in `requirements.txt`.")
        return ""

# --- PDF Upload Section ---
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file is not None:
    st.success("PDF file uploaded successfully!")

    extracted_text = extract_text_from_pdf(uploaded_file)

    if not extracted_text:
        st.warning("Could not extract any meaningful text from the PDF, even with OCR attempts. Please check the PDF content.")
        st.stop()

    st.text_area("Extracted Text (first 1000 characters):", extracted_text[:1000], height=200, help="This shows a preview of the text extracted from your PDF.")

    # --- Generate Synopsis using Gemini ---
    st.subheader("Generating Meeting Synopsis...")

    # Prepare the prompt for Gemini with instructions for detailed and formatted output
    prompt = f"""
    You are an AI assistant specialized in summarizing meeting notes.
    Please read the following text extracted from a PDF document, which contains meeting information.
    Your task is to provide a detailed and properly formatted synopsis of the meeting.

    Please structure your response with the following sections using Markdown headings and bullet points:

    # Meeting Synopsis

    ## Summary
    Provide a concise overview of the entire meeting.

    ## Main Topics Discussed
    List the key subjects or agendas that were covered during the meeting using bullet points.

    ## Key Decisions Made
    Outline any important decisions, agreements, or conclusions reached, using bullet points.

    ## Action Items and Next Steps
    Detail specific tasks assigned, who is responsible (if mentioned), and deadlines (if any), using bullet points.

    ## Attendees (if identifiable)
    List any notable attendees or departments mentioned in the document.

    ---
    Here is the text from the PDF:

    {extracted_text}
    ---

    """

    # Display a spinner while generating
    with st.spinner("Please wait, Gemini is generating the detailed synopsis... This might take a moment for larger PDFs."):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')

            response = model.generate_content(prompt)

            if response.candidates:
                synopsis = response.candidates[0].content.parts[0].text
                st.subheader("🎉 Meeting Synopsis:")
                st.markdown(synopsis) # Streamlit renders Markdown nicely

                # --- Download as Word document ---
                st.subheader("Download Options")
                doc = Document()
                doc.add_heading('Meeting Synopsis', level=0)

                for line in synopsis.split('\n'):
                    if line.startswith('## '):
                        doc.add_heading(line[3:].strip(), level=2)
                    elif line.startswith('# '):
                        doc.add_heading(line[2:].strip(), level=1)
                    elif line.startswith('- '):
                        doc.add_paragraph(line[2:].strip(), style='List Bullet')
                    else:
                        doc.add_paragraph(line.strip())

                doc_buffer = io.BytesIO()
                doc.save(doc_buffer)
                doc_buffer.seek(0)

                st.download_button(
                    label="Download Detailed Synopsis as Word (docx)",
                    data=doc_buffer,
                    file_name="detailed_meeting_synopsis.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )

            else:
                st.error("Could not generate a synopsis. No candidates found in the Gemini response.")
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                    st.warning(f"Gemini blocked the prompt due to: {response.prompt_feedback.block_reason}")
                    st.warning("Please try a different PDF or adjust the content.")
        except Exception as e:
            st.error(f"An error occurred while calling the Gemini API: {e}")
            st.info("Please check your API key, internet connection, or if the PDF content is too large for the model's context window.")

