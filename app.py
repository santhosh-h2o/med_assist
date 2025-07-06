from h2o_wave import main, app, Q, ui
import uuid
import os
import tempfile
from h2ogpte import H2OGPTE
import logging
from fpdf import FPDF

# Silence everything except your own logger
for noisy_logger in ['h2ogpte', 'urllib3', 'h2o', 'werkzeug', 'asyncio']:
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

# Optional: suppress all loggers by default
logging.basicConfig(level=logging.CRITICAL)
global logger
# Then enable only your logger
logger = logging.getLogger('med-assist')
logger.setLevel(logging.DEBUG)

# GPTe configuration
GPTE_ENDPOINT = "https://h2ogpte.internal.dedicated.h2o.ai"
KEY = "sk-Mf20Y6GGRi9VWsATBFoqZK4HvXw3bI0FcFFJDiaHTXonPcxg"  

def analyze_uploaded_document(file_path):
    try:
        client = H2OGPTE(address=GPTE_ENDPOINT, api_key=KEY, verify=False)
        collection_id = client.create_collection(
            name=f'med_analysis_{uuid.uuid4()}',
            description='Medical document analysis'
        )
        
        if not os.path.exists(file_path):
            logger.error(f"File not found at path: {file_path}")
            return "Error: The uploaded file could not be found on the server."
            
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            logger.error(f"File is empty: {file_path}")
            return "Error: The uploaded file is empty."
        with open(file_path, 'rb') as f:
            file_name = os.path.basename(file_path)
            upload_id = client.upload(file_name, f)
        client.ingest_uploads(collection_id, [upload_id])
        chat_session_id = client.create_chat_session(collection_id)
        with client.connect(chat_session_id) as session:
            reply = session.query(
                """Please analyze the uploaded medical document and provide a structured explanation using the format below.
                
                [HEADER] Overview
                [EXPLANATION] Provide a brief summary of what this medical document contains, in simple language a patient can understand.
                
                [HEADER] Key Findings
                [EXPLANATION] Summarize the most important values and results in plain English. Explain what these results mean for the patient's health.
                
                [HEADER] Abnormal Results
                [EXPLANATION] Highlight any abnormal values or concerning findings. Explain what these might mean, but avoid causing unnecessary alarm.
                
                [HEADER] Normal Results
                [EXPLANATION] Briefly mention which values are within normal ranges and what that means for the patient.
                
                [HEADER] Medical Terms Explained
                [EXPLANATION] Define any medical terminology used in the document in simple, everyday language.
                
                [HEADER] Recommended Next Steps
                [EXPLANATION] Suggest appropriate follow-up actions based on these results.
                
                Important: Use everyday language throughout. Avoid medical jargon when possible, and when medical terms must be used, explain them clearly."""
            )
        return reply.content

    except Exception as e:
        print(f"Error in GPTe analysis: {str(e)}")
        return f"Error analyzing document: {str(e)}"


@app('/')
async def serve(q: Q):
    if not q.client.initialized:
        q.page['meta'] = ui.meta_card(box='', title='Med Assist with GPTe', theme='h2o-dark')
        q.page['header'] = ui.header_card(
            box='1 1 12 1',
            title=' Med Assist with GPTe',
            subtitle='Upload your lab report for AI-powered analysis',
            icon='HealthSolid',
            icon_color='#ff5722'
        )
        q.page['upload'] = ui.form_card(
            box='1 2 12 5',
            items=[
                ui.text_xl('Upload Medical Document'),
                ui.file_upload(
                    name='document_upload',
                    label='Choose file',
                    multiple=False  
                ),
                ui.text_xs('Supported formats: PDF, JPG, PNG, TXT')
            ]
        )
        q.client.initialized = True

    if q.args.document_upload:
        try:
            file = q.args.document_upload[0]
            
            if isinstance(file, str):
                file_path = file
                file_name = os.path.basename(file_path)
                
                local_path = await q.site.download(file_path, tempfile.gettempdir())
                file_path = local_path
            else:
                file_name = file.name
                file_path = os.path.join(tempfile.gettempdir(), file_name)
                with open(file_path, 'wb') as f:
                    f.write(file.content)
            
            analysis = analyze_uploaded_document(file_path)
            
            q.client.file_name = file_name
            q.client.file_path = file_path
            q.client.analysis = analysis
            
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    if len(content) > 5000:
                        content = content[:5000] + "...[content truncated]"
                    q.client.file_content = content
            except:
                content = "[File content cannot be displayed - binary format]"
                q.client.file_content = content
            
            q.page['notification'] = ui.form_card(
                box='1 7 12 1',
                items=[
                    ui.message_bar(
                        type='info',
                        text=f'Processed file with GPTe.'
                    )
                ]
            )
            
            q.page['analysis'] = ui.form_card(
                box='1 8 12 6',
                items=[
                    ui.text_xl('GPTe Analysis Results'),
                    ui.text_l(f'Document: {q.client.file_name}'),
                    ui.textbox(
                        name='analysis_text',
                        label='AI-Generated Report (editable):',
                        value=q.client.analysis,
                        multiline=True,
                        height='300px',
                        spellcheck=True,
                    ),
                    ui.buttons([
                        ui.button(name='regenerate_button', label='Regenerate Analysis'),
                        ui.button(name='download_button', label='Download Report as PDF', primary=True),
                        ui.button(name='new_upload_button', label='Upload New Document')
                    ])
                ]
            )
            
            

        except Exception as e:
            logger.error(f"File processing error: {str(e)}", exc_info=True)
            error_message = f"Error processing file: {str(e)}"
            if "permission" in str(e).lower():
                error_message = "Permission error: Unable to save or read the file."
            elif "format" in str(e).lower():
                error_message = "Format error: The file format may not be supported."
            
            q.page['notification'] = ui.form_card(
                box='1 7 12 1',
                items=[
                    ui.message_bar(
                        type='error',
                        text=error_message
                    )
                ]
            )

    if q.args.download_button:
        analysis_text = q.args.analysis_text
        
        # Create a professional PDF without patient information
        from fpdf import FPDF
        from datetime import datetime
        
        class PDF(FPDF):
            def header(self):
                # Company name/logo in header
                self.set_font('Arial', 'B', 20)
                self.set_text_color(25, 82, 118)  # Dark blue color
                self.cell(0, 10, 'MEDICAL ASSOCIATES', 0, 1, 'C')
                self.set_font('Arial', 'B', 15)
                self.set_text_color(0, 0, 0)  # Black color
                self.cell(0, 10, 'Medical Report', 0, 1, 'C')
                # Line break
                self.ln(5)
                # Add a horizontal line
                self.set_draw_color(200, 200, 200)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(10)
            
            def footer(self):
                # Add a horizontal line
                self.set_draw_color(200, 200, 200)
                self.line(10, 270, 200, 270)
                # Position at 1.5 cm from bottom
                self.set_y(-15)
                # Arial italic 8
                self.set_font('Arial', 'I', 8)
                self.set_text_color(128, 128, 128)  # Gray color
                # Disclaimer text
                self.cell(0, 10, 'This report was interpreted by AI and may be incorrect. Please consult with your healthcare provider.', 0, 0, 'C')
        
        # Create PDF instance
        pdf = PDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Add only the date
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%B %d, %Y')}", 0, 1)
        pdf.ln(5)
        
        # Add the analysis text with better formatting
        pdf.set_font('Arial', '', 12)
        
        # Process the text paragraph by paragraph for better formatting
        paragraphs = analysis_text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                # Check if this looks like a heading (all caps or ends with colon)
                if para.isupper() or para.rstrip().endswith(':'):
                    pdf.set_font('Arial', 'B', 12)
                    pdf.multi_cell(0, 10, para)
                    pdf.set_font('Arial', '', 12)
                else:
                    pdf.multi_cell(0, 10, para)
                pdf.ln(5)
        
        # Generate a generic filename with timestamp
        report_filename = f"medical_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf.output(report_filename)
        
        # Upload to Wave server and provide download link
        download_path, = await q.site.upload([report_filename])
        q.page['download'] = ui.form_card(
            box='1 15 12 1',
            items=[
                ui.message_bar(type='success', text='Medical report generated successfully!'),
                ui.link(label='Download Medical Report', path=download_path, download=True, button=True, target='_blank')
            ]
        )

    if q.args.regenerate_button:
        if q.client.file_path:
            analysis = analyze_uploaded_document(q.client.file_path)
            q.client.analysis = analysis
            q.page['analysis'].items[2].value = analysis
            q.page['notification'] = ui.form_card(
                box='1 7 12 1',
                items=[
                    ui.message_bar(type='info', text='Analysis regenerated.')
                ]
            )

    if q.args.new_upload_button:
        for key in ['file_name', 'file_path', 'analysis', 'file_content']:
            if hasattr(q.client, key):
                delattr(q.client, key)
        q.page.drop('analysis', 'document_view', 'notification')
        await q.page.save()
        await serve(q)
        return

    await q.page.save()
