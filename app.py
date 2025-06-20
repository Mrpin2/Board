import streamlit as st
import google.generativeai as genai
import PyPDF2
import io
from docx import Document # Import the Document class from python-docx

# --- Streamlit Secrets Configuration ---
# To use this application, you need to create a file named `.streamlit/secrets.toml`
# in the same directory as your `app.py` file for local development.
# For Streamlit Cloud, you configure these secrets directly in the app dashboard.
#
# Add your API keys and the password to this file like this:
#
# # .streamlit/secrets.toml
# GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
# STREAMLIT_PASSWORD = "Rajeev" # <-- Add this line for your password
# # OPENAI_API_KEY = "YOUR_OPENAI_API_KEY" # Uncomment and add if you plan to use OpenAI API later

# --- Password Protection ---
# Retrieve the correct password from Streamlit secrets
correct_password = st.secrets.get("STREAMLIT_PASSWORD")

if not correct_password:
    st.error("Password not found in Streamlit secrets. Please set `STREAMLIT_PASSWORD`.")
    st.stop() # Stop the execution of the app if password is not set

password = st.sidebar.text_input("Enter Password to Access", type="password")

if password != correct_password:
    st.sidebar.error("Incorrect password. Please try again.")
    st.stop() # Stop the execution of the app if password is wrong
else:
    st.sidebar.success("Password accepted!")

st.title("📄 Meeting Synopsis from PDF (Powered by Gemini)")
st.write("Upload a meeting minutes PDF, and I'll generate a concise synopsis.")

# --- API Key Initialization ---
gemini_api_key = st.secrets.get("GEMINI_API_KEY")

if not gemini_api_key:
    st.error("Gemini API key not found in Streamlit secrets. Please set `GEMINI_API_KEY`.")
    st.stop()

# Configure the Google Generative AI client
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    st.error(f"Error configuring Gemini API: {e}")
    st.stop()

# --- Optional: Accessing ChatGPT API Key (for future use if needed) ---
# openai_api_key = st.secrets.get("OPENAI_API_KEY")
# if openai_api_key:
#     # You would initialize your OpenAI client here if you were using it
#     # from openai import OpenAI
#     # client = OpenAI(api_key=openai_api_key)
#     st.sidebar.info("OpenAI API key detected in secrets (not currently used for synopsis).")
# else:
#     st.sidebar.warning("OpenAI API key not found in Streamlit secrets.")

# --- PDF Upload Section ---
uploaded_file = st.file_uploader("Upload a PDF file", type=["pdf"])

if uploaded_file is not None:
    st.success("PDF file uploaded successfully!")

    # Read the PDF content
    pdf_reader = None
    try:
        # Use BytesIO to handle the uploaded file
        pdf_file = io.BytesIO(uploaded_file.getvalue())
        pdf_reader = PyPDF2.PdfReader(pdf_file)
    except Exception as e:
        st.error(f"Error reading PDF file: {e}")
        st.stop()

    if pdf_reader:
        text = ""
        # Extract text from all pages
        st.info("Extracting text from PDF pages...")
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as e:
                st.warning(f"Could not extract text from page {page_num + 1}: {e}")

        if not text:
            st.warning("No text could be extracted from the PDF. It might be an image-only PDF or corrupted.")
            st.stop()

        st.text_area("Extracted Text (first 1000 characters):", text[:1000], height=200, help="This shows a preview of the text extracted from your PDF.")

        # --- Generate Synopsis using Gemini ---
        st.subheader("Generating Meeting Synopsis...")

        # Prepare the prompt for Gemini
        # It's crucial to provide clear instructions to the LLM.
        prompt = f"""
        You are an AI assistant specialized in summarizing meeting notes.
        Please read the following text extracted from a PDF document, which contains meeting information.
        Your task is to provide a concise synopsis of the meeting.
        Focus on:
        - Main topics discussed.
        - Key decisions made.
        - Any specific action items or next steps.
        - Important attendees or departments mentioned (if relevant and present).

        Here is the text from the PDF:

        ---
        {text}
        ---

        Meeting Synopsis:
        """

        # Display a spinner while generating
        with st.spinner("Please wait, Gemini is generating the synopsis... This might take a moment for larger PDFs."):
            try:
                # Changed model from 'gemini-pro' to 'gemini-1.5-flash' for broader availability
                model = genai.GenerativeModel('gemini-1.5-flash')

                # Generate content
                response = model.generate_content(prompt)

                if response.candidates:
                    # Access the text from the first candidate
                    synopsis = response.candidates[0].content.parts[0].text
                    st.subheader("🎉 Meeting Synopsis:")
                    st.markdown(synopsis)

                    # --- Download as Word document ---
                    st.subheader("Download Options")
                    # Create a new Word document
                    doc = Document()
                    doc.add_heading('Meeting Synopsis', level=1)
                    doc.add_paragraph(synopsis)

                    # Save the document to a BytesIO object
                    doc_buffer = io.BytesIO()
                    doc.save(doc_buffer)
                    doc_buffer.seek(0) # Rewind the buffer to the beginning

                    st.download_button(
                        label="Download Synopsis as Word (docx)",
                        data=doc_buffer,
                        file_name="meeting_synopsis.docx",
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

